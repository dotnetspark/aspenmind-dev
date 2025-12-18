"""
analytics_tools.py

@ai_function tools for metrics, analytics, and reporting.
"""

import sys
import os
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agent_framework import ai_function


@ai_function
def calculate_generation_success_rate(batch_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate success metrics for a generation batch.
    
    Args:
        batch_items: List of items from a batch
    
    Returns:
        Dictionary with:
        - total_attempts: int
        - successful_generations: int (items that passed quality gate)
        - success_rate: float (percentage)
        - average_attempts_per_item: float
        - diversity_failures: int (items that failed similarity check)
    """
    total = len(batch_items)
    if total == 0:
        return {
            "total_attempts": 0,
            "successful_generations": 0,
            "success_rate": 0.0,
            "average_attempts_per_item": 0.0,
            "diversity_failures": 0
        }
    
    successful = sum(1 for item in batch_items if item.get("quality_tier") in ["gold", "silver", "bronze"])
    diversity_fails = sum(1 for item in batch_items if item.get("similarity_at_generation", 0.0) >= 0.75)
    
    attempts = [item.get("generation_attempt", 1) for item in batch_items]
    avg_attempts = sum(attempts) / len(attempts) if attempts else 1.0
    
    return {
        "total_attempts": total,
        "successful_generations": successful,
        "success_rate": (successful / total) * 100,
        "average_attempts_per_item": avg_attempts,
        "diversity_failures": diversity_fails
    }


@ai_function
def analyze_quality_distribution(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze quality score distribution across dimensions.
    
    Args:
        items: List of items with quality_scores_json field
    
    Returns:
        Dictionary with dimension averages and tier distribution
    """
    import json
    
    dimension_scores = {
        "clarity": [],
        "cognitive_level": [],
        "evidence_alignment": [],
        "plausibility": [],
        "legal_accuracy": [],
        "scenario_quality": [],
        "rationale_quality": [],
        "overall": []
    }
    
    tier_counts = {}
    
    for item in items:
        # Parse quality scores
        scores_json = item.get("quality_scores_json", "{}")
        try:
            scores = json.loads(scores_json) if isinstance(scores_json, str) else scores_json
            for dim in dimension_scores.keys():
                if dim in scores and "score" in scores[dim]:
                    dimension_scores[dim].append(scores[dim]["score"])
        except:
            pass
        
        # Count tiers
        tier = item.get("quality_tier", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    # Calculate averages
    dimension_averages = {}
    for dim, scores in dimension_scores.items():
        dimension_averages[dim] = sum(scores) / len(scores) if scores else 0.0
    
    return {
        "dimension_averages": dimension_averages,
        "tier_distribution": tier_counts,
        "total_items": len(items)
    }


@ai_function
def identify_weak_dimensions(items: List[Dict[str, Any]], threshold: float = 3.5) -> List[str]:
    """
    Identify quality dimensions that consistently score below threshold.
    
    Args:
        items: List of items with quality scores
        threshold: Score threshold for identifying weak dimensions
    
    Returns:
        List of dimension names scoring below threshold
    """
    import json
    
    dimension_scores = {
        "clarity": [],
        "cognitive_level": [],
        "evidence_alignment": [],
        "plausibility": [],
        "legal_accuracy": [],
        "scenario_quality": [],
        "rationale_quality": [],
        "overall": []
    }
    
    for item in items:
        scores_json = item.get("quality_scores_json", "{}")
        try:
            scores = json.loads(scores_json) if isinstance(scores_json, str) else scores_json
            for dim in dimension_scores.keys():
                if dim in scores and "score" in scores[dim]:
                    dimension_scores[dim].append(scores[dim]["score"])
        except:
            pass
    
    weak_dimensions = []
    for dim, scores in dimension_scores.items():
        if scores:
            avg = sum(scores) / len(scores)
            if avg < threshold:
                weak_dimensions.append(f"{dim} (avg: {avg:.2f})")
    
    return weak_dimensions


@ai_function
def track_batch_progress(batch_id: str, current_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Track progress for a generation batch.
    
    Args:
        batch_id: Batch identifier
        current_items: Items generated so far in batch
    
    Returns:
        Dictionary with progress metrics
    """
    total = len(current_items)
    pending_review = sum(1 for item in current_items if item.get("review_status") == "pending_review")
    approved = sum(1 for item in current_items if item.get("review_status") in ["approved", "approved_with_edits"])
    rejected = sum(1 for item in current_items if item.get("review_status") == "rejected")
    
    quality_tiers = {}
    for item in current_items:
        tier = item.get("quality_tier", "unknown")
        quality_tiers[tier] = quality_tiers.get(tier, 0) + 1
    
    return {
        "batch_id": batch_id,
        "total_items": total,
        "pending_review": pending_review,
        "approved": approved,
        "rejected": rejected,
        "quality_distribution": quality_tiers,
        "completion_rate": ((approved + rejected) / total * 100) if total > 0 else 0.0
    }


@ai_function
def generate_batch_report(batch_id: str, items: List[Dict[str, Any]]) -> str:
    """
    Generate a human-readable summary report for a batch.
    
    Args:
        batch_id: Batch identifier
        items: All items in the batch
    
    Returns:
        Formatted string report
    """
    if not items:
        return f"Batch {batch_id}: No items generated"
    
    total = len(items)
    quality_dist = {}
    review_dist = {}
    
    for item in items:
        tier = item.get("quality_tier", "unknown")
        status = item.get("review_status", "unknown")
        quality_dist[tier] = quality_dist.get(tier, 0) + 1
        review_dist[status] = review_dist.get(status, 0) + 1
    
    report_lines = [
        f"=== Batch Report: {batch_id} ===",
        f"Total Items: {total}",
        "",
        "Quality Distribution:",
    ]
    
    for tier in ["gold", "silver", "bronze", "needs_revision"]:
        count = quality_dist.get(tier, 0)
        if count > 0:
            pct = (count / total) * 100
            report_lines.append(f"  {tier}: {count} ({pct:.1f}%)")
    
    report_lines.append("")
    report_lines.append("Review Status:")
    
    for status in ["approved", "approved_with_edits", "pending_review", "rejected"]:
        count = review_dist.get(status, 0)
        if count > 0:
            pct = (count / total) * 100
            report_lines.append(f"  {status}: {count} ({pct:.1f}%)")
    
    return "\n".join(report_lines)
