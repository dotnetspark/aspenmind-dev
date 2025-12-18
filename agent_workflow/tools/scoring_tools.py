"""
scoring_tools.py

@ai_function tools for quality scoring and evaluation.
"""

import sys
import os
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agent_framework import ai_function
from generate_items_v2 import validate_and_refine_item
from retrieval import format_rules_for_prompt, retrieve_all_rubric_rules


@ai_function
def score_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score an exam item across 8 quality dimensions.
    
    Dimensions (0-5 scale):
    - Clarity: Question clarity and readability
    - Cognitive Level: Appropriate difficulty/depth
    - Evidence Alignment: Matches evidence statements
    - Plausibility: Distractors are plausible
    - Legal Accuracy: Legally sound content
    - Scenario Quality: Realistic and relevant scenario
    - Rationale Quality: Clear explanation
    - Overall: Holistic assessment
    
    Args:
        item: Item dictionary with stimulus, stem, options, rationale
    
    Returns:
        Dictionary with:
        - quality_score: float (overall 0-5)
        - quality_tier: str (gold/silver/bronze/needs_revision)
        - quality_scores: Dict of dimension scores
        - improvement_suggestions: List of suggestions
    """
    # Get rubric context for scoring
    all_rules = retrieve_all_rubric_rules()
    rubric_context = format_rules_for_prompt(all_rules)
    
    # Use the scoring function from generate_items_v2
    scored_item = validate_and_refine_item(
        item=item,
        rubric_context=rubric_context,
        topic_code=item.get('topic', ''),
        evidence_statements=item.get('evidence_statements', [])
    )
    
    return scored_item.get('quality', {})


@ai_function
def calculate_quality_tier(overall_score: float) -> str:
    """
    Determine quality tier from overall score.
    
    Args:
        overall_score: Overall quality score (0-5)
    
    Returns:
        Tier: "gold" (≥4.5), "silver" (3.5-4.5), "bronze" (2.5-3.5), "needs_revision" (<2.5)
    """
    if overall_score >= 4.5:
        return "gold"
    elif overall_score >= 3.5:
        return "silver"
    elif overall_score >= 2.5:
        return "bronze"
    else:
        return "needs_revision"


@ai_function
def validate_item_structure(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that an item has all required fields and proper structure.
    
    Args:
        item: Item dictionary to validate
    
    Returns:
        Dictionary with:
        - is_valid: bool
        - missing_fields: List of missing required fields
        - validation_errors: List of validation error messages
    """
    required_fields = ["stimulus", "stem", "options", "correct_answer", "rationale", "topic", "evidence"]
    missing = [f for f in required_fields if not item.get(f)]
    
    errors = []
    
    # Check options structure
    if "options" in item:
        options = item["options"]
        if not isinstance(options, dict):
            errors.append("Options must be a dictionary")
        elif len(options) < 4:
            errors.append("Must have at least 4 options")
        elif not all(k in options for k in ["A", "B", "C", "D"]):
            errors.append("Options must include A, B, C, D")
    
    # Check correct answer
    if "correct_answer" in item and "options" in item:
        if item["correct_answer"] not in item["options"]:
            errors.append(f"Correct answer '{item['correct_answer']}' not in options")
    
    # Check text length
    if "stem" in item and len(item["stem"]) < 10:
        errors.append("Stem is too short")
    
    if "rationale" in item and len(item["rationale"]) < 20:
        errors.append("Rationale is too short")
    
    return {
        "is_valid": len(missing) == 0 and len(errors) == 0,
        "missing_fields": missing,
        "validation_errors": errors
    }


@ai_function
def aggregate_batch_quality(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate quality statistics for a batch of items.
    
    Args:
        items: List of items with quality_score and quality_tier fields
    
    Returns:
        Dictionary with:
        - average_score: float
        - tier_distribution: Dict of counts per tier
        - total_items: int
        - gold_rate: float (percentage)
    """
    if not items:
        return {
            "average_score": 0.0,
            "tier_distribution": {},
            "total_items": 0,
            "gold_rate": 0.0
        }
    
    scores = [item.get("quality_score", 0.0) for item in items]
    tiers = [item.get("quality_tier", "unknown") for item in items]
    
    tier_counts = {}
    for tier in tiers:
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    return {
        "average_score": sum(scores) / len(scores),
        "tier_distribution": tier_counts,
        "total_items": len(items),
        "gold_rate": (tier_counts.get("gold", 0) / len(items)) * 100
    }
