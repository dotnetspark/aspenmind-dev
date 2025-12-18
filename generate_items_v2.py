"""
generate_items_v2.py

JD-Next item generation using:
- FULL rubric context (all rules, not just semantic top-k)
- Similar-item retrieval (exam item index)
- Multi-stage generation with quality scoring
- Index upload for feedback loop

Key improvements over v1:
1. Loads ALL rubric rules instead of just top-k semantic matches
2. Multi-stage generation: Generate -> Score -> Store
3. Structured prompts with categorized rules (DOs, DONTs, etc.)
4. Quality scoring with multi-dimensional rubric assessment
5. Automatic upload to index for future training/retrieval

Requires:
- retrieval.py with comprehensive retrieval functions
"""

import argparse
import json
import sys
import random
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from retrieval import (
    retrieve_similar_items, 
    client, 
    search_rubric, 
    AZURE_OPENAI_CHAT_MODEL,
    retrieve_comprehensive_context,
    format_rules_for_prompt,
    retrieve_all_rubric_rules,
    upload_items_batch,
    upload_item_to_index,
    embed,
)


# ---------------------------------------------------------
# POST-GENERATION PROCESSING (Best Practice)
# ---------------------------------------------------------

def shuffle_answer_options(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Randomly shuffle answer options AFTER generation.
    This is more reliable than instructing the LLM to place answer at specific position.
    
    Why post-processing is better:
    - Deterministic: Always works, no LLM compliance issues
    - Token-efficient: No extra prompt tokens needed
    - Truly random: Each generation is independent
    - Verifiable: We control the final output
    """
    correct = item.get("correct_answer")
    options = item.get("options", {})
    
    if not correct or not options or len(options) != 4:
        return item
    
    # Create position mapping
    positions = ["A", "B", "C", "D"]
    random.shuffle(positions)
    
    # Remap options
    original_order = ["A", "B", "C", "D"]
    shuffled_options = {
        positions[i]: options.get(original_order[i], "")
        for i in range(4)
    }
    
    # Update correct answer position
    try:
        correct_idx = original_order.index(correct)
        new_correct = positions[correct_idx]
    except (ValueError, IndexError):
        # If correct answer not found, keep original
        return item
    
    item["options"] = shuffled_options
    item["correct_answer"] = new_correct
    
    return item


def validate_and_fix_evidence_statements(
    item: Dict[str, Any], 
    evidence_map: Dict[str, str]
) -> Dict[str, Any]:
    """
    Auto-fix evidence statements that only contain codes.
    
    Post-processing validation is better than relying on LLM instructions because:
    - Guaranteed correctness
    - Handles edge cases
    - Self-healing system
    """
    evidence_statements = item.get("evidence_statements", [])
    fixed = []
    
    for stmt in evidence_statements:
        stmt = stmt.strip()
        # If it's just a code like "2.e", expand it
        if ":" not in stmt:
            # Try to find matching code
            matched = False
            for code, text in evidence_map.items():
                if stmt == code or stmt.startswith(code):
                    fixed.append(f"{code}: {text}")
                    matched = True
                    break
            if not matched:
                # Keep original if no match
                fixed.append(stmt)
        else:
            fixed.append(stmt)
    
    item["evidence_statements"] = fixed
    return item


def calculate_scenario_similarity(text1: str, text2: str) -> float:
    """
    Calculate semantic similarity between two scenarios using embeddings.
    Returns cosine similarity (0-1, where 1 = identical).
    """
    if not text1 or not text2:
        return 0.0
    
    try:
        # Truncate to first 200 chars for efficiency
        emb1 = np.array(embed(text1[:200]))
        emb2 = np.array(embed(text2[:200]))
        
        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(similarity)
    except Exception as e:
        print(f"[WARNING] Similarity calculation failed: {e}", file=sys.stderr)
        return 0.0


def check_scenario_diversity(
    new_item: Dict[str, Any],
    previous_items: List[Dict[str, Any]],
    threshold: float = 0.75
) -> Tuple[bool, float]:
    """
    Check if new scenario is sufficiently different from previous ones.
    
    Returns: (is_diverse, max_similarity)
    
    Why semantic check is better than string comparison:
    - Detects conceptually similar scenarios even with different wording
    - Quantifiable metric
    - Tunable threshold
    """
    new_stimulus = new_item.get("stimulus", "")
    
    if not previous_items or not new_stimulus:
        return True, 0.0
    
    max_similarity = 0.0
    for prev_item in previous_items:
        prev_stimulus = prev_item.get("stimulus", "")
        if prev_stimulus:
            similarity = calculate_scenario_similarity(new_stimulus, prev_stimulus)
            max_similarity = max(max_similarity, similarity)
    
    is_diverse = max_similarity < threshold
    return is_diverse, max_similarity


# ---------------------------------------------------------
# CORE GENERATION FUNCTION (MULTI-STAGE)
# ---------------------------------------------------------

def generate_jdnext_item(
    topic_code: str,
    evidence_statements: List[str],
    comprehensive_context: Dict[str, Any],
    temperature: float = 0.4,
    validate: bool = True,
    previous_scenarios: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate a single JD-Next item aligned to a specific topic and evidence statement.
    Uses FULL rubric rules (all categories) and similar items as context.
    Implements multi-stage generation: Generate -> Score -> Post-process.
    
    Args:
        previous_scenarios: Brief descriptions of previously generated scenarios to avoid repetition
    
    Returns a dict representing the item, or None if parsing fails.
    
    Note: Answer position randomization happens in post-processing via shuffle_answer_options().
    """

    # Extract context components
    all_rules = comprehensive_context.get("all_rules", {})
    topic_definition = comprehensive_context.get("topic_definition")
    relevant_examples = comprehensive_context.get("relevant_examples", [])
    similar_items = comprehensive_context.get("similar_items", [])
    
    # Format ALL rubric rules into structured sections
    rubric_context = format_rules_for_prompt(all_rules)
    
    # Count rules for debugging
    total_rules = sum(len(rules) for rules in all_rules.values())
    print(f"[DEBUG] Loaded {total_rules} rubric rules across {len(all_rules)} categories")

    # Format topic definition
    topic_context = ""
    if topic_definition:
        topic_context = f"\nTopic Definition: {topic_definition.get('content', '')}"

    # Format relevant examples (from semantic search)
    example_context_lines = []
    for ex in relevant_examples:
        example_context_lines.append(
            f"[{ex.get('category', '')} | {ex.get('subsection', '')}]\n{ex.get('content', '')}"
        )
    example_context = "\n\n".join(example_context_lines) if example_context_lines else "No specific examples retrieved."

    # Format retrieved high-quality items
    item_context_lines = []
    for r in similar_items:
        item_context_lines.append(
            "HIGH-QUALITY REFERENCE ITEM:\n"
            f"  Topic: {r.get('topic', '')} | Evidence: {r.get('evidence', '')}\n"
            f"  Question: {r.get('question_text', '')}\n"
            f"  Options: {r.get('options_raw', '')}\n"
            f"  Correct: {r.get('correct_answer', '')}\n"
            f"  Rationale: {r.get('rationale', '')}"
        )
    item_context = "\n\n".join(item_context_lines) if item_context_lines else "No reference items available."

    # System prompt with FULL rubric (rubric-driven, JSON-only)
    system_prompt = f"""You are the JD-Next Item Generator - an expert psychometrician creating high-quality legal exam items.

Your job is to create a new, high-quality, psychometrically defensible multiple-choice exam item
that aligns to the specified JD-Next topic and evidence statement.

CRITICAL: You MUST follow ALL rubric rules below. These are non-negotiable requirements.

{rubric_context}

=== GENERATION PROCESS ===
Before outputting, you MUST mentally verify:
1. ✓ Stimulus is clear, accessible, and provides enough context for legal reasoning
2. ✓ Stem asks a clear, direct question requiring application of legal principles
3. ✓ Exactly ONE answer is unambiguously correct (the "key")
4. ✓ All three distractors are plausible but definitively wrong
5. ✓ No construct-irrelevant variance (difficulty comes from legal reasoning, not language)
6. ✓ Item aligns precisely to the topic and evidence statement
7. ✓ Language is plain English, fair, and accessible to all US test takers
8. ✓ No inappropriate content (violence, controversy, stereotypes, luxury, dated references)
9. ✓ Options are parallel in structure and length
10. ✓ Rationale explains why key is correct AND why each distractor is wrong

=== OUTPUT FORMAT ===
Return the item in this exact JSON structure:

{{
  "stimulus": "...",
  "stem": "...",
  "options": {{
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  }},
  "correct_answer": "A|B|C|D",
  "rationale": "...",
  "topic": "{topic_code}",
  "evidence_statements": [...]
}}

IMPORTANT RULES:
- evidence_statements MUST include the FULL text, e.g. "2.e: Understand the concept of adequacy..." NOT just "2.e"
- Do not include any extra keys.
- Do not wrap the JSON in Markdown code blocks.
""".strip()

    # Build diversity context
    diversity_context = ""
    if previous_scenarios:
        scenarios_list = "\n".join(f"- {s}" for s in previous_scenarios)
        diversity_context = f"""
=== SCENARIO DIVERSITY REQUIREMENT ===
The following scenarios have ALREADY been used. You MUST create a DIFFERENT scenario:
{scenarios_list}

Use a completely different:
- Setting (e.g., if previous used "business sale", use "employment", "real estate", "services", "family arrangement")
- Relationship type (e.g., if previous used "buyer/seller", use "employer/employee", "landlord/tenant", "neighbors")
- Subject matter (e.g., if previous used "car", use "house", "services", "intellectual property", "goods")
"""

    # User message with structured context
    user_message = f"""Generate a new JD-Next item.

=== TARGET ===
Topic code: {topic_code}
{topic_context}
Evidence statements: {", ".join(evidence_statements)}
{diversity_context}
=== RELEVANT EXAMPLES (for pattern reference only) ===
{example_context}

=== HIGH-QUALITY REFERENCE ITEMS (for style reference only - do NOT copy) ===
{item_context}

=== INSTRUCTIONS ===
Generate ONE new item that:
1. Fits the topic and evidence statement precisely
2. Follows ALL rubric rules (DOs and DONTs)
3. Is NOT a copy or trivial variation of any reference item
4. Has a unique, interesting stimulus that is fair and accessible
5. Has exactly 4 options with one clear key and three plausible distractors
6. evidence_statements array must contain FULL text like "2.e: Understand the concept..." NOT just the code

Output only the JSON. No explanations before or after.
""".strip()

    # Stage 1: Generate initial item
    print("[Stage 1] Generating initial item...")
    response = client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
    )

    content = response.choices[0].message.content.strip()
    
    # Clean up potential markdown code blocks
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    try:
        item = json.loads(content)
    except Exception as e:
        print("Failed to parse generated item as JSON:", e, file=sys.stderr)
        print("Raw model output:\n", content, file=sys.stderr)
        return None

    # Stage 2: Validate and refine (optional)
    if validate:
        item = validate_and_refine_item(item, rubric_context, topic_code, evidence_statements)

    return item


def validate_and_refine_item(
    item: Dict[str, Any],
    rubric_context: str,
    topic_code: str,
    evidence_statements: List[str],
) -> Dict[str, Any]:
    """
    Stage 2: Score the generated item against rubric dimensions.
    Returns the item with quality scores and improvement suggestions.
    
    Scoring dimensions (1-5 scale each):
    - stimulus_score: Clarity, context, appropriateness
    - stem_score: Directness, no negative stems, legal reasoning required
    - key_score: Unambiguously correct, defensible
    - distractors_score: Plausible, parallel, definitively wrong
    - alignment_score: Topic and evidence alignment
    - language_score: Plain English, grammar, accessibility
    - style_score: Format rules, option structure
    - fairness_score: No bias, universally relatable
    
    Overall quality_score = weighted average (1-5)
    Quality tier: "gold" (4.5+), "silver" (3.5-4.5), "bronze" (2.5-3.5), "needs_revision" (<2.5)
    """
    print("[Stage 2] Scoring item against rubric dimensions...")
    
    scoring_prompt = f"""You are a JD-Next Psychometric Quality Scorer. Score the following exam item against rubric dimensions.

=== RUBRIC RULES ===
{rubric_context}

=== ITEM TO SCORE ===
{json.dumps(item, indent=2)}

=== TARGET ===
Topic: {topic_code}
Evidence: {", ".join(evidence_statements)}

=== SCORING INSTRUCTIONS ===
Score each dimension from 1-5:
- 5 = Excellent, exemplary quality, no issues
- 4 = Good, minor improvements possible
- 3 = Acceptable, some issues but usable
- 2 = Below standard, significant issues
- 1 = Poor, major violations, needs rewrite

For each dimension, provide:
1. A numeric score (1-5)
2. Brief justification (1-2 sentences)
3. Specific violations or issues found (if any)

=== OUTPUT FORMAT (JSON only) ===
{{
  "scores": {{
    "stimulus": {{
      "score": <1-5>,
      "justification": "...",
      "issues": ["issue1", "issue2"] or []
    }},
    "stem": {{
      "score": <1-5>,
      "justification": "...",
      "issues": []
    }},
    "key": {{
      "score": <1-5>,
      "justification": "...",
      "issues": []
    }},
    "distractors": {{
      "score": <1-5>,
      "justification": "...",
      "issues": []
    }},
    "alignment": {{
      "score": <1-5>,
      "justification": "...",
      "issues": []
    }},
    "language": {{
      "score": <1-5>,
      "justification": "...",
      "issues": []
    }},
    "style": {{
      "score": <1-5>,
      "justification": "...",
      "issues": []
    }},
    "fairness": {{
      "score": <1-5>,
      "justification": "...",
      "issues": []
    }}
  }},
  "overall_score": <weighted average 1-5>,
  "quality_tier": "gold|silver|bronze|needs_revision",
  "summary": "Brief overall assessment",
  "improvement_suggestions": ["suggestion1", "suggestion2"]
}}

Output only valid JSON. No markdown code blocks.
""".strip()

    response = client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_MODEL,
        messages=[
            {"role": "user", "content": scoring_prompt},
        ],
        temperature=0.2,  # Low temperature for consistent scoring
    )

    scoring_result = response.choices[0].message.content.strip()
    
    # Clean up potential markdown
    if scoring_result.startswith("```json"):
        scoring_result = scoring_result[7:]
    if scoring_result.startswith("```"):
        scoring_result = scoring_result[3:]
    if scoring_result.endswith("```"):
        scoring_result = scoring_result[:-3]
    scoring_result = scoring_result.strip()
    
    try:
        quality_assessment = json.loads(scoring_result)
        
        # Add quality metadata to the item
        item["quality"] = {
            "scores": quality_assessment.get("scores", {}),
            "overall_score": quality_assessment.get("overall_score", 0),
            "quality_tier": quality_assessment.get("quality_tier", "unscored"),
            "summary": quality_assessment.get("summary", ""),
            "improvement_suggestions": quality_assessment.get("improvement_suggestions", []),
            "scored_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
        
        tier = item["quality"]["quality_tier"]
        score = item["quality"]["overall_score"]
        print(f"[Scoring] Item scored: {score:.2f}/5.0 - Tier: {tier.upper()}")
        
        # Log any critical issues
        all_issues = []
        for dim, data in quality_assessment.get("scores", {}).items():
            all_issues.extend(data.get("issues", []))
        if all_issues:
            print(f"[Scoring] Issues found: {len(all_issues)}")
            for issue in all_issues[:3]:  # Show first 3
                print(f"  - {issue}")
        
    except Exception as e:
        print(f"[Scoring] Failed to parse scoring response: {e}", file=sys.stderr)
        # Add minimal quality metadata
        item["quality"] = {
            "overall_score": 0,
            "quality_tier": "unscored",
            "error": str(e),
            "scored_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
    
    return item


# ---------------------------------------------------------
# BATCH GENERATION
# ---------------------------------------------------------

def generate_items_batch(
    topic_code: str,
    count: int,
    retrieval_k: int = 8,
    temperature: float = 0.4,
    validate: bool = True,
) -> List[Dict[str, Any]]:
    """
    Generate multiple JD-Next items for a given topic.
    Uses comprehensive retrieval to get ALL rubric rules plus semantic examples.
    
    Returns a list of item dicts (only those successfully parsed).
    """

    # Build retrieval query
    query_text = f"JD-Next multiple-choice item aligned to topic {topic_code}"

    # Get comprehensive context (ALL rules + semantic examples + similar items)
    print(f"[INFO] Retrieving comprehensive context for topic {topic_code}...")
    comprehensive_context = retrieve_comprehensive_context(
        topic_code=topic_code,
        query_text=query_text,
        k_examples=5,
        k_items=retrieval_k
    )

    items: List[Dict[str, Any]] = []
    previous_items: List[Dict[str, Any]] = []  # Track full items for semantic diversity
    
    # Generate unique batch ID for this generation session
    import uuid
    generation_batch_id = str(uuid.uuid4())

    for i in range(count):
        print(f"\n{'='*50}")
        print(f"Generating item {i + 1}/{count} for topic {topic_code}...")
        print(f"{'='*50}")

        evidence_statements = get_evidence_statements_for_topic(topic_code)
        
        # Build previous scenarios list (first 150 chars for context)
        previous_scenarios = [
            prev.get("stimulus", "")[:150] + "..."
            for prev in previous_items[-3:]  # Only last 3 for token efficiency
            if prev.get("stimulus")
        ] if previous_items else None
        
        # Retry logic for diversity enforcement (max 2 retries = 3 total attempts)
        MAX_RETRIES = 2
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                print(f"[RETRY] Attempt {attempt + 1}/{MAX_RETRIES + 1} due to scenario similarity...")

            item = generate_jdnext_item(
                topic_code=topic_code,
                evidence_statements=evidence_statements,
                comprehensive_context=comprehensive_context,
                temperature=temperature,
                validate=validate,
                previous_scenarios=previous_scenarios,
            )
            
            if item is None:
                print(f"[FAILED] Item {i + 1} failed to parse on attempt {attempt + 1}.", file=sys.stderr)
                if attempt == MAX_RETRIES:
                    print(f"[SKIP] Skipping item {i + 1} after {MAX_RETRIES + 1} failed attempts.")
                    break
                continue
            
            # Post-processing: Fix evidence statements
            item = validate_and_fix_evidence_statements(item, EVIDENCE_MAP)
            
            # Post-processing: Shuffle answer positions (truly random)
            original_answer = item.get("correct_answer", "?")
            item = shuffle_answer_options(item)
            new_answer = item.get("correct_answer", "?")
            
            # Check scenario diversity - ENFORCE with retry
            max_similarity = 0.0
            is_diverse = True
            if previous_items:
                is_diverse, max_similarity = check_scenario_diversity(item, previous_items, threshold=0.75)
                
                if not is_diverse and attempt < MAX_RETRIES:
                    print(f"[REJECT] Scenario similarity: {max_similarity:.3f} (threshold: 0.75) - retrying...")
                    continue  # Retry with new generation
                elif not is_diverse and attempt == MAX_RETRIES:
                    print(f"[WARNING] Scenario similarity: {max_similarity:.3f} after {MAX_RETRIES + 1} attempts - accepting anyway.")
            
            # Add generation metadata for tracking
            item["generation_batch_id"] = generation_batch_id
            item["generation_attempt"] = attempt + 1
            item["similarity_at_generation"] = max_similarity
            
            # Success - add to collection
            items.append(item)
            previous_items.append(item)
            print(f"[SUCCESS] Item {i + 1} generated (attempt {attempt + 1}, similarity: {max_similarity:.3f}).")
            break  # Exit retry loop

    return items


# ---------------------------------------------------------
# EVIDENCE STATEMENTS MAP
# ---------------------------------------------------------

EVIDENCE_MAP = {
    "1.a": "Understand what expectation damages are and what function they serve.",
    "1.b": "Understand the purpose of expectation damages.",
    "1.c": "Calculate expectation damages in a given scenario.",
    "2.a": "Apply the legal test for consideration, including both elements of legal value and bargained-for-exchange.",
    "2.b": "Understand what is meant by 'legal value' and 'bargained-for-exchange.'",
    "2.c": "Identify the legal detriment to the promisee and/or legal benefit to the promisor in a given fact pattern.",
    "2.d": "Identify what is meant by the term 'consideration' in the context of contracts and gifts.",
    "2.e": "Understand the concept of adequacy of consideration and the principle of 'freedom of contract.'",
    "2.f": "Understand why courts, as a general rule, do not inquire into the adequacy of consideration.",
    "3.a": "Distinguish between a gratuitous promise and a contract supported by consideration.",
    "3.b": "Identify elements that make a promise gratuitous.",
    "4.a": "Identify past consideration and explain why it does not support a contract.",
    "4.b": "Distinguish past consideration from valid consideration.",
    "5.a": "Identify an illusory promise and explain why it cannot serve as consideration.",
    "5.b": "Distinguish between illusory and non-illusory promises.",
    "6.a": "Apply the objective theory of contracts to determine mutual assent.",
    "6.b": "Distinguish between objective and subjective intent.",
    "7.a": "Identify the elements of a valid offer.",
    "7.b": "Distinguish between bilateral and unilateral contracts.",
    "8.a": "Identify valid acceptance of an offer.",
    "8.b": "Apply the mailbox rule to determine when acceptance is effective.",
    "9.a": "Apply promissory estoppel to enforce a promise lacking consideration.",
    "9.b": "Identify the elements required for promissory estoppel.",
}


def get_evidence_statements_for_topic(topic_code: str) -> List[str]:
    """
    Retrieve random evidence statements for a given topic code.
    """
    topic_suffix = topic_code.split(".")[1] if "." in topic_code else topic_code
    matching = [
        f"{code}: {statement}"
        for code, statement in EVIDENCE_MAP.items()
        if code.startswith(topic_suffix + ".")
    ]
    # Randomly select 1, 2, or 3 (max) evidence statements
    k = min(len(matching), random.choice([1, 2, 3]))
    return random.sample(matching, k) if matching else [f"Evidence for topic {topic_code}"]


def load_valid_topics():
    """Load valid topic codes from the rubric index."""
    results = search_rubric.search(
        search_text=None,
        filter="category eq 'TOPIC'",
        select=["subsection"],
    )
    return {r["subsection"] for r in results}


def validate_topic(topic_code: str):
    """Validate that the topic code exists in the rubric."""
    valid_topics = load_valid_topics()
    if topic_code not in valid_topics:
        raise ValueError(
            f"Unknown topic code '{topic_code}'. "
            f"Valid topics are: {sorted(valid_topics)}"
        )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate JD-Next exam items using full rubric context (v2)."
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="JD-Next topic code (e.g., TP.3)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of items to generate (default: 1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write generated items as JSONL",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.4,
        help="Sampling temperature (default: 0.4)",
    )
    parser.add_argument(
        "--retrieval-k",
        type=int,
        default=8,
        help="Number of similar items to retrieve (default: 8)",
    )
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="Skip the scoring stage (faster but no quality metadata)",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload generated items to the exam index (enables feedback loop)",
    )
    parser.add_argument(
        "--upload-min-score",
        type=float,
        default=0.0,
        help="Only upload items with quality score >= this value (default: 0.0 = upload all)",
    )
    parser.add_argument(
        "--upload-quality-threshold",
        type=str,
        default="bronze",
        choices=["gold", "silver", "bronze", "all"],
        help="Upload items meeting this quality tier or higher (default: bronze = 2.5+). 'all' uploads everything.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    topic_code = args.topic
    count = args.count
    temperature = args.temperature
    retrieval_k = args.retrieval_k
    output_path = args.output
    score = not args.no_score
    upload = args.upload
    upload_min_score = args.upload_min_score
    upload_quality_threshold = args.upload_quality_threshold

    validate_topic(topic_code)

    print(f"\n{'='*60}")
    print(f"JD-Next Item Generator v2 (Full Rubric Context)")
    print(f"{'='*60}")
    print(f"Topic: {topic_code}")
    print(f"Count: {count}")
    print(f"Scoring: {'Enabled' if score else 'Disabled'}")
    print(f"Upload to Index: {'Enabled' if upload else 'Disabled'}")
    if upload:
        if upload_min_score > 0:
            print(f"Upload Min Score: {upload_min_score}")
        print(f"Upload Quality Threshold: {upload_quality_threshold}")
    print(f"{'='*60}\n")

    items = generate_items_batch(
        topic_code=topic_code,
        count=count,
        retrieval_k=retrieval_k,
        temperature=temperature,
        validate=score,  # 'validate' param now means 'score'
    )

    print(f"\n{'='*60}")
    print(f"Generated {len(items)} items.")
    
    # Show quality summary
    if score:
        tier_counts = {}
        for item in items:
            tier = item.get("quality", {}).get("quality_tier", "unscored")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        print(f"Quality Distribution: {tier_counts}")
    
    # Show answer distribution (should be roughly balanced)
    answer_counts = {}
    for item in items:
        ans = item.get("correct_answer", "unknown")
        answer_counts[ans] = answer_counts.get(ans, 0) + 1
    print(f"Answer Distribution: {answer_counts}")
    
    print(f"{'='*60}")

    # Upload to index if requested
    if upload:
        print(f"\n{'='*60}")
        print(f"Uploading items to exam index with status 'pending_review'...")
        print(f"{'='*60}")
        
        # Define tier thresholds
        tier_thresholds = {
            "gold": 4.5,
            "silver": 3.5,
            "bronze": 2.5,
            "all": 0.0,
        }
        
        # Filter by quality tier threshold
        min_score_threshold = tier_thresholds.get(upload_quality_threshold, 2.5)
        items_to_upload = items
        
        if upload_min_score > 0:
            # Use explicit min score if provided (overrides tier threshold)
            items_to_upload = [
                item for item in items 
                if item.get("quality", {}).get("overall_score", 0) >= upload_min_score
            ]
            print(f"Filtered to {len(items_to_upload)} items with score >= {upload_min_score}")
        elif upload_quality_threshold != "all":
            # Use tier-based threshold
            items_to_upload = [
                item for item in items 
                if item.get("quality", {}).get("overall_score", 0) >= min_score_threshold
            ]
            print(f"Filtered to {len(items_to_upload)} items with quality tier >= {upload_quality_threshold} (score >= {min_score_threshold})")
        
        if items_to_upload:
            # Upload with pending_review status for human review
            upload_result = upload_items_batch(items_to_upload, review_status="pending_review")
            print(f"Upload Results:")
            print(f"  - Total: {upload_result['total']}")
            print(f"  - Succeeded: {upload_result['succeeded']}")
            print(f"  - Failed: {upload_result['failed']}")
            print(f"  - By Tier: {upload_result['by_tier']}")
            print(f"  - Review Status: pending_review (awaiting human review)")
            
            # Show any errors
            for r in upload_result['results']:
                if not r['success']:
                    print(f"  - Error uploading {r['id']}: {r['error']}")
        else:
            threshold_desc = f"{upload_quality_threshold} tier" if upload_quality_threshold != "all" else f"score >= {upload_min_score}"
            print(f"No items met the threshold ({threshold_desc})")

    # Write to file if requested
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"\nWrote items to {output_path}")
    else:
        # Print to stdout as JSONL
        print("\n=== GENERATED ITEMS ===")
        for item in items:
            print(json.dumps(item, indent=2, ensure_ascii=False))
            print()


if __name__ == "__main__":
    main()