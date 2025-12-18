"""
review_tools.py

@ai_function tools for human review workflow and state management.
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agent_framework import ai_function
from retrieval import (
    upload_item_to_index,
    update_review_status,
    get_pending_review_items,
    get_approved_items,
    get_rejection_patterns,
    get_review_analytics
)


@ai_function
def upload_item_for_review(item: Dict[str, Any], review_status: str = "pending_review") -> Dict[str, str]:
    """
    Upload an item to Azure Search with specified review status.
    
    Args:
        item: Item dictionary with all fields
        review_status: Status for review workflow (default: "pending_review")
            Options: "gold_standard", "pending_review", "approved", "approved_with_edits", "rejected"
    
    Returns:
        Dictionary with:
        - status: "success" or "error"
        - item_id: The uploaded item's ID
        - message: Success/error message
    """
    try:
        result = upload_item_to_index(item, review_status=review_status)
        return {
            "status": "success",
            "item_id": item.get("id", "unknown"),
            "message": f"Item uploaded with review_status={review_status}"
        }
    except Exception as e:
        return {
            "status": "error",
            "item_id": item.get("id", "unknown"),
            "message": str(e)
        }


@ai_function
def submit_review_decision(
    item_id: str,
    decision: str,
    explanation: str,
    reviewed_by: str,
    edited_fields: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Submit a human review decision for an item.
    
    Args:
        item_id: ID of the item being reviewed
        decision: Review decision ("approved", "approved_with_edits", "rejected")
        explanation: Human explanation for the decision
        reviewed_by: Email/ID of the reviewer
        edited_fields: Dictionary of fields that were edited (if any)
    
    Returns:
        Dictionary with:
        - status: "success" or "error"
        - new_review_status: The updated review status
        - message: Confirmation message
    """
    try:
        update_review_status(
            item_id=item_id,
            decision=decision,
            explanation=explanation,
            reviewed_by=reviewed_by,
            edited_fields=edited_fields
        )
        return {
            "status": "success",
            "new_review_status": decision,
            "message": f"Review decision '{decision}' recorded for item {item_id}"
        }
    except Exception as e:
        return {
            "status": "error",
            "new_review_status": "unknown",
            "message": str(e)
        }


@ai_function
def fetch_pending_reviews(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch items awaiting human review.
    
    Args:
        limit: Maximum number of items to retrieve
    
    Returns:
        List of item dictionaries with review_status="pending_review"
    """
    return get_pending_review_items(limit=limit)


@ai_function
def fetch_approved_items(limit: int = 50, include_edits: bool = True) -> List[Dict[str, Any]]:
    """
    Fetch items that have been approved by reviewers.
    
    Args:
        limit: Maximum number of items to retrieve
        include_edits: Include items that were edited during review
    
    Returns:
        List of approved item dictionaries
    """
    return get_approved_items(limit=limit, include_edits=include_edits)


@ai_function
def analyze_rejections(topic: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Analyze patterns in rejected items to improve future generation.
    
    Args:
        topic: Optional topic filter (e.g., "TP.2")
        limit: Maximum number of rejected items to analyze
    
    Returns:
        List of rejected items with review explanations
    """
    return get_rejection_patterns(topic=topic, limit=limit)


@ai_function
def get_review_metrics() -> Dict[str, Any]:
    """
    Get aggregate review metrics and analytics.
    
    Returns:
        Dictionary with:
        - total_reviewed: int
        - approval_rate: float (percentage)
        - edit_rate: float (percentage of approvals that required edits)
        - quality_by_status: Dict mapping review_status to average quality scores
        - common_rejection_reasons: List of frequent rejection explanations
    """
    return get_review_analytics()


@ai_function
def batch_upload_items(
    items: List[Dict[str, Any]],
    review_status: str = "pending_review",
    quality_threshold: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload multiple items to Azure Search with filtering by quality tier.
    
    Args:
        items: List of item dictionaries
        review_status: Review status to assign (default: "pending_review")
        quality_threshold: Optional filter - only upload items meeting tier
            Options: "gold", "silver", "bronze", "all" (None = no filter)
    
    Returns:
        Dictionary with:
        - uploaded_count: int
        - skipped_count: int
        - items_uploaded: List of uploaded item IDs
    """
    tier_hierarchy = {"needs_revision": 0, "bronze": 1, "silver": 2, "gold": 3}
    threshold_level = tier_hierarchy.get(quality_threshold, -1) if quality_threshold and quality_threshold != "all" else -1
    
    uploaded = []
    skipped = []
    
    for item in items:
        # Check quality threshold
        if threshold_level > -1:
            item_tier = item.get("quality_tier", "needs_revision")
            item_level = tier_hierarchy.get(item_tier, 0)
            if item_level < threshold_level:
                skipped.append(item.get("id", "unknown"))
                continue
        
        # Upload item
        try:
            upload_item_to_index(item, review_status=review_status)
            uploaded.append(item.get("id", "unknown"))
        except Exception as e:
            skipped.append(f"{item.get('id', 'unknown')} (error: {str(e)})")
    
    return {
        "uploaded_count": len(uploaded),
        "skipped_count": len(skipped),
        "items_uploaded": uploaded,
        "items_skipped": skipped
    }
