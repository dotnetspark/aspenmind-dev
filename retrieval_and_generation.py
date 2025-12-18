import argparse
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
AZURE_OPENAI_CHAT_MODEL = "gpt-4o"

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")

# ------------------------------------------------------------
# EVIDENCE STATEMENT MAP
# ------------------------------------------------------------

EVIDENCE_MAP = {
    "01.02.01" : "Apply the legal test for consideration, including both elements of legal value and bargained-for-exchange.",
    "01.02.02" : "Understand what is meant by 'legal value' and 'bargained-for-exchange.'",
    "01.02.03" : "Identify the legal detriment to the promisee and/or legal benefit to the promisor in a given fact pattern.",
    "01.02.04" : "Identify what is meant by the term 'consideration' in the context of contracts and gifts.",
    "01.02.05" : "Understand the concept of adequacy of consideration and the principle of 'freedom of contract.'",
    "01.02.06" : "Understand why courts, as a general rule, do not inquire into the adequacy of consideration."
}

def get_evidence_text(evidence_prefix: str) -> str:
    """
    Returns all Evidence Statements whose codes start with the given prefix, formatted as 'code: statement'.
    Example: prefix '01.02' returns '01.02.01: ...', '01.02.02: ...', etc.
    """
    matched = [
        f"{code} - {text}" for code, text in EVIDENCE_MAP.items()
        if code.startswith(evidence_prefix)
    ]
    if not matched:
        raise ValueError(f"No evidence statements found for prefix '{evidence_prefix}'.")
    return "\n".join(matched)

# ------------------------------------------------------------
# CLIENTS
# ------------------------------------------------------------

client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX,
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)
)

index_client = SearchIndexClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)
)

# ------------------------------------------------------------
# EMBEDDING
# ------------------------------------------------------------

def embed(text: str):
    response = client.embeddings.create(
        model=AZURE_OPENAI_EMBEDDING_MODEL,
        input=text
    )
    embedding = response.data[0].embedding
    assert len(embedding) == 1536, f"Embedding length is {len(embedding)}, expected 1536"
    return embedding

# ------------------------------------------------------------
# RETRIEVAL
# ------------------------------------------------------------

def retrieve_examples(query, k=5):
    vector = embed(query)

    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=k,
        fields="content_vector"
    )

    results = search_client.search(
        search_text=None,              # or a lexical string for hybrid
        vector_queries=[vector_query],
        select=["full_text"],
    )

    return [r["full_text"] for r in results]

# ------------------------------------------------------------
# GENERATION
# ------------------------------------------------------------

def build_user_prompt(
    evidence_statements: str,
    examples: list[str],
    topic_query: str,
    num_items: int
) -> str:
        examples_block = "\n\n".join(examples)

        prompt = f'''
You are generating high-quality exam items aligned to specific Evidence Statements in contract law.

Topic focus:
- Target topic: "{topic_query}"
- Only generate items that are clearly about this topic AND that can be supported by at least one Evidence Statement below.
- Do not introduce issues, doctrines, or jurisdictions that are clearly unrelated to the Evidence Statements.

Available Evidence Statements:
{evidence_statements}

Here are example items for style only (do NOT copy or paraphrase):
{examples_block}

Below are three full examples showing correct use of 1, 2, and 3 evidence statements and overall structure. Treat these examples as the gold standard for the level of detail, alignment, and clarity expected.

Example with 1 evidence statement:
{{
    "evidence_statements": [
        "01.02.01 - Apply the legal test for consideration, including both elements of legal value and bargained-for-exchange."
    ],
    "scenario": "Taylor agrees to fix Morgan's car in exchange for $500. Taylor completes the repairs as agreed.",
    "question": "Which element of consideration is present in this agreement?",
    "options": {{
        "A": "Taylor's promise to fix the car is a legal detriment.",
        "B": "Morgan's promise to pay $500 is a legal detriment.",
        "C": "Taylor's act of fixing the car is a legal benefit.",
        "D": "There is no consideration present."
    }},
    "correct_option": "A",
    "rationale": "Taylor's promise to fix the car represents a legal detriment, fulfilling the element of legal value in a bargained-for exchange."
}}

Example with 2 evidence statements:
{{
    "evidence_statements": [
        "01.02.01 - Apply the legal test for consideration, including both elements of legal value and bargained-for-exchange.",
        "01.02.03 - Identify the legal detriment to the promisee and/or legal benefit to the promisor in a given fact pattern."
    ],
    "scenario": "Alex promises to deliver a rare book to Jamie if Jamie agrees to paint Alex's fence. Jamie paints the fence, but Alex refuses to deliver the book. Both parties understood the terms and agreed in writing.",
    "question": "Which elements of consideration are present in this agreement?",
    "options": {{
        "A": "Jamie's act of painting the fence is a legal detriment, and Alex's promise to deliver the book is a legal benefit.",
        "B": "Only Jamie's act is relevant to consideration.",
        "C": "Only Alex's promise is relevant to consideration.",
        "D": "There is no consideration present."
    }},
    "correct_option": "A",
    "rationale": "Jamie's act is a legal detriment and Alex's promise is a legal benefit, satisfying the legal test for consideration."
}}

Example with 3 evidence statements:
{{
    "evidence_statements": [
        "01.02.01 - Apply the legal test for consideration, including both elements of legal value and bargained-for-exchange.",
        "01.02.03 - Identify the legal detriment to the promisee and/or legal benefit to the promisor in a given fact pattern.",
        "01.02.05 - Understand the concept of adequacy of consideration and the principle of 'freedom of contract.'"
    ],
    "scenario": "Jordan agrees to sell a painting to Casey for $10, even though the painting is worth $1,000. Casey promises to deliver a set of rare books to Jordan as part of the deal. Both parties sign a contract.",
    "question": "Which legal principles are illustrated by this agreement?",
    "options": {{
        "A": "The adequacy of consideration is not relevant, and both parties have provided legal value.",
        "B": "The contract is void due to inadequate consideration.",
        "C": "Only Casey's promise is relevant to consideration.",
        "D": "There is no legal detriment present."
    }},
    "correct_option": "A",
    "rationale": "Both parties have provided legal value and detriment, and the court will not inquire into the adequacy of consideration, respecting the freedom of contract."
}}


Out-of-scope behavior:
- If the topic is clearly outside the scope of these Evidence Statements, respond with:

OUT_OF_SCOPE
<brief explanation of why>

- Do NOT return OUT_OF_SCOPE just because it is difficult to create scenarios or because some scenarios feel similar.

Item count behavior:
- If you cannot generate {num_items} unique items that meet all requirements, generate as many valid, unique items as you can (even if fewer than {num_items}).
- Always maximize the number of valid, unique items in your response.

Generation task:
- Otherwise, generate up to {num_items} NEW exam items in the following machine-readable format.

Format:
- Output a JSON array.
- Each element must be an object with the following keys:
    - "evidence_statements": array of 1–3 strings. Each string must be copied exactly (including both the code and the text, e.g., "01.02.01 - Apply the legal test for consideration, including both elements of legal value and bargained-for exchange.") from the provided Evidence Statements list.
    - "scenario": string, 3–7 sentences, describing a realistic but fictional situation.
    - "question": string, one clear question about the scenario.
    - "options": object with keys "A", "B", "C", "D", each a plausible answer and mutually exclusive.
    - "correct_option": one of "A", "B", "C", "D".
    - "rationale": string that explains why the correct option is correct by reference to the Evidence Statement(s), and briefly why the other options are not correct.

Requirements:
- Use only Evidence Statements from the provided list; do not invent new ones or modify their wording.
- Randomly select 1, 2, or 3 Evidence Statements per item. At least 30% of items must use 2 or 3 Evidence Statements combined.
- Ensure all items are unique in surface wording. It is acceptable if some scenarios or legal issues are similar, as long as the wording and context differ.
- If you cannot generate enough unique legal scenarios, create additional items by varying the names of parties, businesses, and factual details, while keeping the legal issue and evidence alignment. Do not repeat the exact same scenario text.
- Ensure the scenario clearly implicates each listed Evidence Statement; avoid tagging evidence that is only tangentially related.
- Do not reuse or closely paraphrase any example content.
- Ensure legal accuracy and clear alignment with the chosen Evidence Statements.
- Avoid trick questions; the correct option must be unambiguously correct under the Evidence Statements.
- Avoid real person or organization names; use generic or fictional names only.
- Do not provide real-world legal advice or procedural guidance; focus only on the exam-style analysis implied by the Evidence Statements.
- Return ONLY valid JSON or the OUT_OF_SCOPE format described above.
- Output only raw JSON (no surrounding commentary, no code fences, no triple backticks).
'''.strip()

        return prompt

def generate_exam_items(evidence_statements: str,
                        topic_query: str,
                        num_items: int = 20) -> str:
    # 1. Retrieve example items for style
    examples = retrieve_examples(topic_query, k=5)

    # 2. Build the user-facing task prompt
    user_prompt = build_user_prompt(
        evidence_statements=evidence_statements,
        examples=examples,
        topic_query=topic_query,
        num_items=num_items
    )

    # 3. Call the chat model with a system + user message
    response = client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": """
You are an expert assessment item writer specializing in generating legally accurate,
scenario-based multiple-choice items for professional exams in contract law.

Your goals:
- Strictly align every item to the provided Evidence Statements.
- Follow the required output schema exactly.
- Refuse or return OUT_OF_SCOPE when the request cannot be satisfied safely or within scope.

Guardrails:
- Use only generally accepted legal principles for the specified jurisdiction if given; if no jurisdiction is specified,
  assume mainstream U.S. contract law at a bar-exam style level.
- Do not provide actual legal advice, instructions for real-world legal strategy, or jurisdiction-specific procedural guidance.
- Do not include real person names, real organizations, or real case citations; use generic names and entities only.
- Avoid discriminatory, defamatory, or clearly inappropriate scenarios.
""".strip(),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.7,
    )

    content = response.choices[0].message.content

    # Optional: you can parse/validate JSON or detect OUT_OF_SCOPE here.
    # For now, just return the raw content.
    return content

# ------------------------------------------------------------
# CLI / MAIN
# ------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Generate exam items using Azure Search + Azure OpenAI.")
    parser.add_argument(
        "--evidence-prefix",
        type=str,
        required=True,
        help="Evidence code prefix (e.g., '01.02' or '01.02.01')."
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help='Natural language topic query for retrieval (e.g., "consideration in contract law").'
    )
    parser.add_argument(
        "--num-items",
        type=int,
        default=20,
        help="Number of exam items to generate (default: 20)."
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    evidence_text = get_evidence_text(args.evidence_prefix)

    output = generate_exam_items(
        evidence_statements=evidence_text,
        topic_query=args.topic,
        num_items=args.num_items
    )

    # Prepare output directory and filename
    os.makedirs("output", exist_ok=True)
    # Clean evidence prefix for filename (replace spaces with underscores, remove special chars)
    safe_prefix = "_".join(args.evidence_prefix.lower().split())
    safe_prefix = "".join(c for c in safe_prefix if c.isalnum() or c == "_")
    timespan = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"output/{safe_prefix}_{args.num_items}_{timespan}.json"

    try:
        parsed = json.loads(output)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        print(f"✅ Output saved to {filename}")
    except Exception:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"⚠️ Output not valid JSON, saved as text to {filename}")