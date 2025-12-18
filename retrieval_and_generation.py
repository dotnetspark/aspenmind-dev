import argparse
import os
import json
import time
from dotenv import load_dotenv
from datetime import datetime
from openai import AzureOpenAI, RateLimitError
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

load_dotenv()

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

Below is one example showing the correct structure and alignment between the scenario, question, options, rationale, and evidence statements.

Example:
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

Out-of-scope behavior:
- If the topic is clearly outside the scope of these Evidence Statements, respond with:

OUT_OF_SCOPE
<brief explanation of why>

- Do NOT return OUT_OF_SCOPE just because it is difficult to create scenarios or because some scenarios feel similar.

Item count behavior:
- Your goal is to generate EXACTLY {num_items} items that meet all requirements.
- Only generate fewer than {num_items} if you reach a hard limit (for example, the response becomes too long to continue). In that case, still maximize the number of valid, unique items in your response.

Generation task:
- Otherwise, generate EXACTLY {num_items} NEW exam items in the following machine-readable format.

Format:
- Output a JSON array.
- Each element must be an object with the following keys:
    - "evidence_statements": array of 1–3 strings. Each string must be copied exactly (including both the code and the text, e.g., "01.02.01 - Apply the legal test for consideration, including both elements of legal value and bargained-for exchange.") from the provided Evidence Statements list.
    - "scenario": string, 3–7 sentences, describing a realistic but fictional situation.
    - "question": string, one clear question about the scenario.
    - "options": object with keys "A", "B", "C", "D", each a plausible answer and mutually exclusive.
    - "correct_option": one of "A", "B", "C", "D".
    - "rationale": 1–2 sentences that explain why the correct option is correct by reference to the Evidence Statement(s).

Requirements:
- Use only Evidence Statements from the provided list; do not invent new ones or modify their wording.

Evidence selection requirements:
- For each item, select 1, 2, or 3 Evidence Statements from the provided list.
- You MUST use a mix of 1, 2, and 3 Evidence Statements across all items.
- At least 30% of items MUST use 2 or 3 Evidence Statements.
- You MUST NOT make all items use only 1 Evidence Statement.
- Before finalizing your answer, count how many items use 1, 2, and 3 Evidence Statements.
  - If fewer than 30% of items use 2 or 3 Evidence Statements, revise the items so that at least 30% do.

- Ensure all items are unique in surface wording. You may reuse similar legal issues as long as the wording and specific facts differ.
- If you run out of genuinely distinct legal scenarios, you may vary names of parties, businesses, and factual details, while keeping the legal issue and evidence alignment. Do not repeat the exact same scenario text.
- Ensure each scenario clearly implicates every listed Evidence Statement; avoid tagging evidence that is only tangentially related.
- Do not reuse or closely paraphrase any example content.
- Ensure legal accuracy and clear alignment with the chosen Evidence Statements.
- Avoid trick questions; the correct option must be unambiguously correct under the Evidence Statements.
- Avoid real person or organization names; use generic or fictional names only.
- Do not provide real-world legal advice or procedural guidance; focus only on exam-style analysis implied by the Evidence Statements.
- Return ONLY valid JSON or the OUT_OF_SCOPE format described above.
- Output only raw JSON (no surrounding commentary, no code fences, no triple backticks).
'''.strip()

        return prompt


def call_with_backoff(func, *args, **kwargs):
    max_retries = 6
    delay = 2
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            sleep_time = delay * (2 ** attempt)
            print(f"Rate limit hit. Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
        except Exception as e:
            # Also backoff for transient errors
            if attempt == max_retries - 1:
                raise
            sleep_time = delay * (2 ** attempt)
            print(f"Error: {e}. Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

def generate_exam_items_batches(evidence_statements: str,
                               topic_query: str,
                               num_items: int = 20,
                               batch_size: int = 5,
                               max_batch_tokens: int = 48000):
    # Retrieve example items for style (once)
    examples = retrieve_examples(topic_query, k=5)

    total_generated = 0
    batch_num = 0
    while total_generated < num_items:
        batch_num += 1
        # Adjust batch size if close to the end
        current_batch_size = min(batch_size, num_items - total_generated)
        user_prompt = build_user_prompt(
            evidence_statements=evidence_statements,
            examples=examples,
            topic_query=topic_query,
            num_items=current_batch_size
        )

        # Exponential backoff for each batch
        response = call_with_backoff(
            client.chat.completions.create,
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
        # Token usage monitoring
        usage = getattr(response, 'usage', None)
        total_tokens = usage.total_tokens if usage and hasattr(usage, 'total_tokens') else None
        print(f"Batch {batch_num}: generated {current_batch_size} items. Tokens used: {total_tokens}")

        # If OUT_OF_SCOPE, yield as a single line
        if content.strip().startswith("OUT_OF_SCOPE"):
            yield {"OUT_OF_SCOPE": content.strip()}
            return

        # Try to parse as JSON array
        try:
            items = json.loads(content)
            if isinstance(items, list):
                for item in items:
                    yield item
                total_generated += len(items)
            else:
                yield {"error": "Expected a list of items", "raw": content}
                total_generated += 1
        except Exception as e:
            yield {"error": f"Failed to parse JSON: {e}", "raw": content}
            total_generated += 1

        # If token usage is close to the limit, start a new batch
        if total_tokens and total_tokens >= max_batch_tokens:
            print(f"Token usage {total_tokens} close to limit, starting new batch.")
            continue

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
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of items to generate per batch (default: 5)."
    )
    parser.add_argument(
        "--max-batch-tokens",
        type=int,
        default=48000,
        help="Maximum tokens per batch before starting a new batch (default: 48000, just under 50K)."
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    evidence_text = get_evidence_text(args.evidence_prefix)

    # Prepare output directory and filename
    os.makedirs("output", exist_ok=True)
    safe_prefix = "_".join(args.evidence_prefix.lower().split())
    safe_prefix = "".join(c for c in safe_prefix if c.isalnum() or c == "_")
    filename = f"output/{args.evidence_prefix}_{args.num_items}.jsonl"

    # Resume support: check for existing items
    existing_items = []
    existing_hashes = set()
    max_id = 0
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line)
                    # Use scenario+question as a unique hash for deduplication
                    if isinstance(item, dict) and "scenario" in item and "question" in item:
                        h = hash(item["scenario"] + item["question"])
                        existing_hashes.add(h)
                        existing_items.append(item)
                        # Track max id if present
                        if "id" in item:
                            try:
                                max_id = max(max_id, int(item["id"]))
                            except Exception:
                                pass
                except Exception:
                    continue

    count = len(existing_items)
    print(f"Resuming from {count} items in {filename} (if exists). Target: {args.num_items}")

    # Ensure file ends with a newline before appending
    if os.path.exists(filename):
        with open(filename, "rb+") as f_check:
            f_check.seek(0, os.SEEK_END)
            if f_check.tell() > 0:
                f_check.seek(-1, os.SEEK_END)
                last_char = f_check.read(1)
                if last_char != b"\n":
                    f_check.write(b"\n")

    with open(filename, "a", encoding="utf-8") as f:
        for item in generate_exam_items_batches(
            evidence_statements=evidence_text,
            topic_query=args.topic,
            num_items=args.num_items,
            batch_size=args.batch_size,
            max_batch_tokens=args.max_batch_tokens
        ):
            # Deduplicate by scenario+question hash
            if isinstance(item, dict) and "scenario" in item and "question" in item:
                h = hash(item["scenario"] + item["question"])
                if h in existing_hashes:
                    continue
                existing_hashes.add(h)
                # Add a unique id for traceability
                item["id"] = max_id + 1
                max_id += 1
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            count += 1
            if count >= args.num_items:
                break
    print(f"✅ {count} items saved to {filename} (JSONL)")