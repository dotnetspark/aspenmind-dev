"""
generation_tools.py

@ai_function tools for item generation with rubric and similarity context.
These wrap existing functions from the parent directory's retrieval and generation modules.
"""

import sys
import os
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to import existing modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agent_framework import ai_function
from retrieval import (
    retrieve_rubric_chunks,
    retrieve_similar_items,
    embed,
    retrieve_comprehensive_context
)

# Import generation functions from parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from generate_items_v2 import (
    generate_jdnext_item,
    calculate_scenario_similarity,
    check_scenario_diversity
)

# Add config directory to path for evidence mapping
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.evidence_map import get_evidence_for_topic as get_evidence_statements_static

# Cache rubric rules to avoid repeated fetching
_RUBRIC_CACHE = {}

def get_cached_comprehensive_context(topic_code: str, query_text: str, k_examples: int = 5, k_items: int = 8):
    """Get comprehensive context with caching for rubric rules."""
    cache_key = topic_code
    
    if cache_key not in _RUBRIC_CACHE:
        logger.info(f"[CACHE MISS] Loading rubric rules for {topic_code}")
        _RUBRIC_CACHE[cache_key] = retrieve_comprehensive_context(
            topic_code=topic_code,
            query_text=query_text,
            k_examples=k_examples,
            k_items=k_items
        )
    else:
        logger.info(f"[CACHE HIT] Using cached rubric rules for {topic_code}")
    
    return _RUBRIC_CACHE[cache_key]


@ai_function
def generate_item_with_context(
    topic_code: str,
    evidence_statements: List[str],
    temperature: float = 0.4
) -> Dict[str, Any]:
    """
    Generate a JD-Next exam item with rubric rules and similar items as context.
    
    Args:
        topic_code: Topic code (e.g., "TP.2")
        evidence_statements: List of evidence statement texts
        temperature: Generation temperature (0.0-1.0)
    
    Returns:
        Dictionary containing the generated item with all fields
    """
    logger.info(f"[TOOL CALL] generate_item_with_context(topic_code={topic_code}, temperature={temperature})")
    logger.info(f"[TOOL CALL] Evidence statements: {len(evidence_statements)}")  # Log count
    
    # Retrieve comprehensive context with caching
    comprehensive_context = get_cached_comprehensive_context(
        topic_code=topic_code,
        query_text=f"Topic {topic_code}: {' '.join(evidence_statements[:2])}",
        k_examples=5,
        k_items=8
    )
    
    # Generate item using the full generation pipeline
    item = generate_jdnext_item(
        topic_code=topic_code,
        evidence_statements=evidence_statements,
        comprehensive_context=comprehensive_context,
        temperature=temperature,
        validate=True  # Include quality scoring
    )
    
    logger.info(f"[TOOL RESULT] Item generated - Quality: {item.get('quality', {}).get('quality_tier', 'unscored')}")
    return item


@ai_function
def check_diversity(
    new_item_stimulus: str,
    previous_stimuli: List[str],
    similarity_threshold: float = 0.75
) -> Dict[str, Any]:
    """
    Check if a new item stimulus is sufficiently different from existing items.
    
    Args:
        new_item_stimulus: The stimulus text of the new item to check
        previous_stimuli: List of stimulus texts from previously generated items
        similarity_threshold: Maximum allowed similarity (default: 0.75)
    
    Returns:
        Dictionary with:
        - is_diverse: bool (True if sufficiently different)
        - max_similarity: float (highest similarity found)
        - message: str (explanation)
    """
    logger.info(f"[TOOL CALL] check_diversity(previous_count={len(previous_stimuli)}, threshold={similarity_threshold})")
    
    if not previous_stimuli:
        logger.info("[TOOL RESULT] No previous items - diversity check passed")
        return {
            "is_diverse": True,
            "max_similarity": 0.0,
            "message": "No previous items to compare against"
        }
    
    # Calculate similarity against each previous stimulus
    max_similarity = 0.0
    for prev_stimulus in previous_stimuli:
        similarity = calculate_scenario_similarity(new_item_stimulus, prev_stimulus)
        max_similarity = max(max_similarity, similarity)
    
    is_diverse = max_similarity < similarity_threshold
    
    logger.info(f"[TOOL RESULT] Diversity check: {'PASSED' if is_diverse else 'FAILED'} - max_similarity={max_similarity:.3f}")
    
    return {
        "is_diverse": is_diverse,
        "max_similarity": float(max_similarity),
        "message": f"Similarity: {max_similarity:.3f} (threshold: {similarity_threshold})"
    }


@ai_function
def retry_generation_for_diversity(
    topic_code: str,
    evidence_statements: List[str],
    previous_attempts: List[Dict[str, Any]],
    attempt_number: int,
    max_attempts: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Retry item generation with increased temperature to enforce diversity.
    
    Args:
        topic_code: Topic code
        evidence_statements: Evidence statements
        previous_attempts: List of previously generated items that failed diversity check
        attempt_number: Current attempt number (1-indexed)
        max_attempts: Maximum retry attempts
    
    Returns:
        New item dict or None if max attempts exceeded
    """
    if attempt_number > max_attempts:
        return None
    
    # Increase temperature with each attempt to encourage diversity
    base_temp = 0.4
    temperature = min(0.9, base_temp + (attempt_number - 1) * 0.2)
    
    # Generate with higher temperature
    return generate_item_with_context(
        topic_code=topic_code,
        evidence_statements=evidence_statements,
        temperature=temperature
    )


@ai_function
def get_rubric_context(topic_code: str, evidence_text: str, k: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve relevant rubric chunks for a topic and evidence.
    
    Args:
        topic_code: Topic code
        evidence_text: Evidence statement text
        k: Number of chunks to retrieve
    
    Returns:
        List of rubric chunk dictionaries with category, subsection, type, content
    """
    query = f"Topic {topic_code}: {evidence_text}"
    return retrieve_rubric_chunks(query, k=k)


@ai_function
def get_evidence_for_topic_code(topic_code: str) -> List[str]:
    """
    Retrieve all evidence statements for a given topic code from static mapping.
    
    Args:
        topic_code: Topic code like "TP.2" or "2"
    
    Returns:
        List of full evidence statements (code + text) for the topic
        
    Examples:
        For "TP.2", returns:
        - "2.a: Apply the legal test for consideration..."
        - "2.b: Understand what is meant by 'legal value'..."
        - etc.
    """
    logger.info(f"[TOOL CALL] get_evidence_for_topic_code(topic_code={topic_code})")
    evidence_list = get_evidence_statements_static(topic_code)
    logger.info(f"[TOOL RESULT] Retrieved {len(evidence_list)} evidence statements")
    return evidence_list


@ai_function
def get_similar_items(topic_code: str, evidence_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve similar existing items for reference.
    
    Args:
        topic_code: Topic code
        evidence_text: Evidence statement text
        k: Number of similar items to retrieve
    
    Returns:
        List of similar item dictionaries
    """
    query = f"Topic {topic_code}: {evidence_text}"
    return retrieve_similar_items(query, k=k)
