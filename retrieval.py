"""
retrieval.py

Handles:
- Embedding queries
- Retrieving rubric chunks from jdnext_rubric_index
- Retrieving similar items from jdnext_exam_items_index
- Full rubric loading for comprehensive rule coverage
"""

import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.search.documents.models import VectorizedQuery


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
AZURE_OPENAI_CHAT_MODEL = "gpt-4o"

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_EXAM_INDEX = os.getenv("AZURE_EXAM_INDEX")
AZURE_RUBRIC_INDEX = os.getenv("AZURE_RUBRIC_INDEX")

# Rubric categories that contain MUST-FOLLOW rules (not examples)
MANDATORY_RULE_CATEGORIES = [
    "CONSTRUCT",
    "ANATOMY", 
    "ITEM_WRITING",
    "LANGUAGE",
    "STIMULUS",
    "ITEM_STYLE",
    "ITEM_REVISION",
]

# Categories for semantic retrieval (examples, before/after)
EXAMPLE_CATEGORIES = [
    "EXAMPLE",
    "BEFORE_AFTER",
]


# ---------------------------------------------------------
# CLIENTS
# ---------------------------------------------------------

search_rubric = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_RUBRIC_INDEX,
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)
)

search_items = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_EXAM_INDEX,
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)
)

client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)


# ---------------------------------------------------------
# EMBEDDING FUNCTION
# ---------------------------------------------------------

def embed(text: str):
    """
    Generate an embedding vector for a query using Azure OpenAI.
    """
    response = client.embeddings.create(
        model=AZURE_OPENAI_EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


# ---------------------------------------------------------
# RUBRIC RETRIEVAL
# ---------------------------------------------------------

def retrieve_rubric_chunks(query_text: str, k: int = 8):
    """
    Retrieve the most relevant rubric chunks from the rubric index.
    NOTE: This only returns k chunks - use retrieve_all_rubric_rules() for full coverage.
    """
    vector = embed(query_text)

    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=k,
        fields="content_vector"
    )

    results = search_rubric.search(
        search_text=None,              # or a lexical string for hybrid
        vector_queries=[vector_query],
        select=[
            "id",
            "category",
            "subsection",
            "type",
            "content",
            "order"
        ]
    )

    return [r for r in results]


# ---------------------------------------------------------
# FULL RUBRIC RETRIEVAL (ALL RULES)
# ---------------------------------------------------------

def retrieve_all_rubric_rules() -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieve ALL rubric rules from the index, organized by category.
    This ensures no rules are missed during item generation.
    
    Returns a dict keyed by category with lists of rule dicts.
    """
    # Query all mandatory rule categories
    filter_expr = " or ".join([f"category eq '{cat}'" for cat in MANDATORY_RULE_CATEGORIES])
    
    results = search_rubric.search(
        search_text="*",  # Match all
        filter=filter_expr,
        select=[
            "id",
            "category",
            "subsection",
            "type",
            "content",
            "order"
        ],
        top=500,  # Ensure we get all rules
        order_by=["order asc"]
    )
    
    # Organize by category
    rules_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        cat = r.get("category", "OTHER")
        if cat not in rules_by_category:
            rules_by_category[cat] = []
        rules_by_category[cat].append(dict(r))
    
    return rules_by_category


def retrieve_rubric_examples(query_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve relevant EXAMPLE and BEFORE_AFTER chunks using semantic search.
    These are topic-specific and benefit from semantic matching.
    """
    vector = embed(query_text)
    
    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=k,
        fields="content_vector"
    )
    
    # Filter to only example categories
    filter_expr = " or ".join([f"category eq '{cat}'" for cat in EXAMPLE_CATEGORIES])
    
    results = search_rubric.search(
        search_text=None,
        vector_queries=[vector_query],
        filter=filter_expr,
        select=[
            "id",
            "category",
            "subsection",
            "type",
            "content",
            "order"
        ]
    )
    
    return [dict(r) for r in results]


def retrieve_topic_definition(topic_code: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the specific topic definition from the rubric.
    """
    results = search_rubric.search(
        search_text=None,
        filter=f"category eq 'TOPIC' and subsection eq '{topic_code}'",
        select=["id", "category", "subsection", "type", "content"]
    )
    
    for r in results:
        return dict(r)
    return None


def format_rules_for_prompt(rules_by_category: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Format all rubric rules into a structured prompt section.
    Organizes rules by category and type for clarity.
    """
    sections = []
    
    # Define the order and formatting for each category
    category_order = [
        ("CONSTRUCT", "CONSTRUCT & VALIDITY RULES"),
        ("ANATOMY", "ITEM ANATOMY REQUIREMENTS"),
        ("ITEM_WRITING", "ITEM WRITING RULES"),
        ("LANGUAGE", "LANGUAGE RULES"),
        ("STIMULUS", "STIMULUS RULES"),
        ("ITEM_STYLE", "ITEM STYLE RULES"),
        ("ITEM_REVISION", "QUALITY ISSUES TO AVOID"),
    ]
    
    for cat_key, cat_title in category_order:
        if cat_key not in rules_by_category:
            continue
            
        rules = rules_by_category[cat_key]
        section_lines = [f"\n=== {cat_title} ==="]
        
        # Group by type within category
        dos = [r for r in rules if r.get("type") in ("DO", "GUIDELINE", "METHOD")]
        donts = [r for r in rules if r.get("type") in ("DONT",)]
        definitions = [r for r in rules if r.get("type") in ("DEFINITION", "PRINCIPLE", "CLARIFICATION")]
        components = [r for r in rules if r.get("type") in ("COMPONENT",)]
        notes = [r for r in rules if r.get("type") in ("NOTE", "TODO", "TODO_DETAIL", "ISSUE")]
        
        if definitions:
            section_lines.append("\nDefinitions & Principles:")
            for r in definitions:
                section_lines.append(f"  • {r['content']}")
        
        if components:
            section_lines.append("\nRequired Components:")
            for r in components:
                section_lines.append(f"  • {r['content']}")
        
        if dos:
            section_lines.append("\nDO:")
            for r in dos:
                section_lines.append(f"  ✓ {r['content']}")
        
        if donts:
            section_lines.append("\nDO NOT:")
            for r in donts:
                section_lines.append(f"  ✗ {r['content']}")
        
        if notes:
            section_lines.append("\nNotes & Warnings:")
            for r in notes:
                section_lines.append(f"  ⚠ {r['content']}")
        
        sections.append("\n".join(section_lines))
    
    return "\n".join(sections)


# ---------------------------------------------------------
# EXAM ITEM RETRIEVAL
# ---------------------------------------------------------

def retrieve_similar_items(query_text: str, k: int = 8):
    """
    Retrieve similar exam items from the exam item index.
    """
    vector = embed(query_text)

    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=k,
        fields="content_vector"
    )

    results = search_items.search(
        search_text=None,              # or a lexical string for hybrid
        vector_queries=[vector_query],
        select=[
            "id",
            "topic",
            "evidence",
            "question_text",
            "options_raw",
            "correct_answer",
            "rationale"
        ]
    )

    return [r for r in results]


# ---------------------------------------------------------
# OPTIONAL: DUAL RETRIEVAL
# ---------------------------------------------------------

def retrieve_dual(query_text: str, k_rubric: int = 8, k_items: int = 8):
    """
    Retrieve both rubric chunks and similar items.
    """
    return {
        "rubric": retrieve_rubric_chunks(query_text, k=k_rubric),
        "items": retrieve_similar_items(query_text, k=k_items)
    }


# ---------------------------------------------------------
# COMPREHENSIVE RETRIEVAL FOR ITEM GENERATION
# ---------------------------------------------------------

def retrieve_comprehensive_context(
    topic_code: str,
    query_text: str,
    k_examples: int = 5,
    k_items: int = 8
) -> Dict[str, Any]:
    """
    Retrieve comprehensive context for high-quality item generation:
    1. ALL rubric rules (not just top-k semantic matches)
    2. Topic-specific examples via semantic search
    3. Similar high-quality items for reference
    4. Topic definition
    
    Returns a structured dict with all context needed for generation.
    """
    return {
        "all_rules": retrieve_all_rubric_rules(),
        "topic_definition": retrieve_topic_definition(topic_code),
        "relevant_examples": retrieve_rubric_examples(query_text, k=k_examples),
        "similar_items": retrieve_similar_items(query_text, k=k_items),
    }


# ---------------------------------------------------------
# INDEX UPLOAD FOR SCORED ITEMS
# ---------------------------------------------------------

def upload_item_to_index(item: Dict[str, Any], review_status: str = "pending_review") -> Dict[str, Any]:
    """
    Upload a scored item to the exam items index with review/state management fields.
    Creates embedding for the item content and includes quality + review metadata.
    
    Args:
        item: Item dictionary with content, quality, and optional generation metadata
        review_status: Initial review status ("pending_review" | "approved" | "gold_standard")
    
    Returns the upload result with success/failure status.
    """
    import uuid
    from datetime import datetime
    
    # Generate unique ID if not present
    item_id = item.get("id") or str(uuid.uuid4())
    
    # Create searchable content from item components
    content_text = f"""
Topic: {item.get('topic', '')}
Evidence: {', '.join(item.get('evidence_statements', []))}
Stimulus: {item.get('stimulus', '')}
Stem: {item.get('stem', '')}
Options: A) {item.get('options', {}).get('A', '')} B) {item.get('options', {}).get('B', '')} C) {item.get('options', {}).get('C', '')} D) {item.get('options', {}).get('D', '')}
Correct: {item.get('correct_answer', '')}
Rationale: {item.get('rationale', '')}
""".strip()
    
    # Generate embedding
    content_vector = embed(content_text)
    
    # Extract quality metadata
    quality = item.get("quality", {})
    
    # Build document for index
    document = {
        "id": item_id,
        "topic": item.get("topic", ""),
        "domain": item.get("domain", ""),  # Added domain field
        "evidence": ", ".join(item.get("evidence_statements", [])),
        "question_text": f"{item.get('stimulus', '')}\n\n{item.get('stem', '')}",
        "full_text": content_text,
        "stimulus": item.get("stimulus", ""),
        "stem": item.get("stem", ""),
        "options_raw": json.dumps(item.get("options", {})),
        "option_a": item.get("options", {}).get("A", ""),
        "option_b": item.get("options", {}).get("B", ""),
        "option_c": item.get("options", {}).get("C", ""),
        "option_d": item.get("options", {}).get("D", ""),
        "correct_answer": item.get("correct_answer", ""),
        "rationale": item.get("rationale", ""),
        "content_vector": content_vector,
        
        # === Quality metadata ===
        "quality_score": quality.get("overall_score", 0),
        "quality_tier": quality.get("quality_tier", "unscored"),
        "quality_summary": quality.get("summary", ""),
        "quality_scores_json": json.dumps(quality.get("scores", {})),
        "improvement_suggestions": quality.get("improvement_suggestions", []),
        
        # === Review & State Management (Human-in-the-Loop) ===
        "review_status": review_status,  # "gold_standard" | "pending_review" | "approved" | "approved_with_edits" | "rejected"
        "reviewed_at": None,
        "reviewed_by": None,
        "review_decision": None,  # "upvote" | "downvote"
        "review_explanation": None,
        
        # === Edit Tracking ===
        "was_edited": False,
        "original_version_json": None,
        "edit_summary": None,
        
        # === Generation Metadata (for Agent Framework + Analytics) ===
        "generation_batch_id": item.get("generation_batch_id"),
        "generation_attempt": item.get("generation_attempt", 1),
        "similarity_at_generation": item.get("similarity_at_generation"),
        "generation_metadata_json": json.dumps(item.get("generation_metadata", {})) if item.get("generation_metadata") else None,
        
        # === Timestamps ===
        "created_at": datetime.utcnow().isoformat() + "Z",
        "scored_at": quality.get("scored_at", ""),
        
        # === Source tracking ===
        "source": item.get("source", "generated_v2"),
        "is_generated": True,
    }
    
    try:
        result = search_items.upload_documents([document])
        success = result[0].succeeded
        return {
            "success": success,
            "id": item_id,
            "quality_tier": quality.get("quality_tier", "unscored"),
            "quality_score": quality.get("overall_score", 0),
            "error": None if success else result[0].error_message,
        }
    except Exception as e:
        return {
            "success": False,
            "id": item_id,
            "error": str(e),
        }


def upload_items_batch(items: List[Dict[str, Any]], review_status: str = "pending_review") -> Dict[str, Any]:
    """
    Upload multiple scored items to the exam items index with specified review status.
    
    Args:
        items: List of item dictionaries to upload
        review_status: Initial review status for all items (default: "pending_review")
    
    Returns summary of upload results.
    """
    results = []
    for item in items:
        result = upload_item_to_index(item, review_status=review_status)
        results.append(result)
    
    succeeded = sum(1 for r in results if r["success"])
    failed = len(results) - succeeded
    
    # Group by quality tier
    tier_counts = {}
    for r in results:
        if r["success"]:
            tier = r.get("quality_tier", "unscored")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    return {
        "total": len(items),
        "succeeded": succeeded,
        "failed": failed,
        "by_tier": tier_counts,
        "results": results,
    }


# ---------------------------------------------------------
# QUALITY-AWARE RETRIEVAL
# ---------------------------------------------------------

def retrieve_items_by_quality(
    query_text: str,
    min_score: float = 0.0,
    max_score: float = 5.0,
    quality_tiers: Optional[List[str]] = None,
    k: int = 8
) -> List[Dict[str, Any]]:
    """
    Retrieve items filtered by quality score and/or tier.
    
    Args:
        query_text: Semantic search query
        min_score: Minimum quality score (0-5)
        max_score: Maximum quality score (0-5)
        quality_tiers: List of tiers to include ["gold", "silver", "bronze", "needs_revision"]
        k: Number of results
    
    Returns items matching the quality criteria.
    """
    vector = embed(query_text)
    
    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=k * 2,  # Fetch more to account for filtering
        fields="content_vector"
    )
    
    # Build filter expression
    filters = []
    if min_score > 0:
        filters.append(f"quality_score ge {min_score}")
    if max_score < 5:
        filters.append(f"quality_score le {max_score}")
    if quality_tiers:
        tier_filter = " or ".join([f"quality_tier eq '{t}'" for t in quality_tiers])
        filters.append(f"({tier_filter})")
    
    filter_expr = " and ".join(filters) if filters else None
    
    results = search_items.search(
        search_text=None,
        vector_queries=[vector_query],
        filter=filter_expr,
        select=[
            "id",
            "topic",
            "evidence",
            "question_text",
            "stimulus",
            "stem",
            "options_raw",
            "correct_answer",
            "rationale",
            "quality_score",
            "quality_tier",
            "quality_summary",
        ],
        top=k
    )
    
    return [dict(r) for r in results]


def retrieve_gold_and_low_quality_items(
    query_text: str,
    k_gold: int = 5,
    k_low: int = 3
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieve both high-quality (gold) and low-quality items for contrastive learning.
    
    This allows the generator to see:
    - Gold items: What TO do (positive examples)
    - Low-quality items: What NOT to do (negative examples)
    
    Returns dict with "gold" and "low_quality" item lists.
    """
    gold_items = retrieve_items_by_quality(
        query_text=query_text,
        quality_tiers=["gold"],
        k=k_gold
    )
    
    low_quality_items = retrieve_items_by_quality(
        query_text=query_text,
        max_score=2.5,
        quality_tiers=["needs_revision", "bronze"],
        k=k_low
    )
    
    return {
        "gold": gold_items,
        "low_quality": low_quality_items,
    }


# ---------------------------------------------------------
# REVIEW & STATE MANAGEMENT (for Agent Framework)
# ---------------------------------------------------------

def update_review_status(
    item_id: str,
    review_decision: str,
    review_explanation: Optional[str] = None,
    reviewed_by: Optional[str] = None,
    edited_fields: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update the review status of an item after human review.
    
    Args:
        item_id: The document ID in the index
        review_decision: "upvote" | "downvote"
        review_explanation: Optional explanation for the decision
        reviewed_by: Optional reviewer identifier
        edited_fields: Optional dict of field updates if item was edited
    
    Returns operation result with success status
    """
    from datetime import datetime
    
    # First, fetch the current item to capture original version if edited
    try:
        current_item = search_items.get_document(key=item_id)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch item: {str(e)}"
        }
    
    # Determine new review status based on decision
    if review_decision == "upvote":
        review_status = "approved_with_edits" if edited_fields else "approved"
    elif review_decision == "downvote":
        review_status = "rejected"
    else:
        return {
            "success": False,
            "error": f"Invalid review_decision: {review_decision}. Must be 'upvote' or 'downvote'."
        }
    
    # Build update document
    update_doc = {
        "id": item_id,
        "review_status": review_status,
        "review_decision": review_decision,
        "review_explanation": review_explanation,
        "reviewed_by": reviewed_by,
        "reviewed_at": datetime.utcnow().isoformat() + "Z",
    }
    
    # Handle edits if present
    if edited_fields:
        # Capture original version before edits (JSON snapshot)
        original_snapshot = {k: current_item.get(k) for k in edited_fields.keys()}
        update_doc["was_edited"] = True
        update_doc["original_version_json"] = json.dumps(original_snapshot)
        update_doc["edit_summary"] = f"Edited fields: {', '.join(edited_fields.keys())}"
        
        # Merge edited fields into update
        update_doc.update(edited_fields)
    else:
        update_doc["was_edited"] = False
    
    # Perform merge_or_upload (updates existing document)
    try:
        result = search_items.merge_or_upload_documents([update_doc])
        success = result[0].succeeded
        return {
            "success": success,
            "item_id": item_id,
            "new_status": review_status,
            "error": None if success else result[0].error_message,
        }
    except Exception as e:
        return {
            "success": False,
            "item_id": item_id,
            "error": str(e),
        }


def get_pending_review_items(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retrieve all items pending human review.
    
    Args:
        limit: Maximum number of items to return
    
    Returns list of items with review_status = "pending_review"
    """
    results = search_items.search(
        search_text="*",
        filter="review_status eq 'pending_review'",
        select=[
            "id", "topic", "evidence", "stimulus", "stem",
            "option_a", "option_b", "option_c", "option_d",
            "correct_answer", "rationale",
            "quality_score", "quality_tier", "quality_summary",
            "generation_batch_id", "generation_attempt", "similarity_at_generation",
            "created_at"
        ],
        order_by=["created_at desc"],
        top=limit
    )
    
    return [dict(r) for r in results]


def get_approved_items(
    limit: int = 100,
    include_edits: bool = True
) -> List[Dict[str, Any]]:
    """
    Retrieve all approved items (with or without edits).
    
    Args:
        limit: Maximum number of items to return
        include_edits: If True, includes both "approved" and "approved_with_edits"
    
    Returns list of approved items
    """
    if include_edits:
        filter_expr = "review_status eq 'approved' or review_status eq 'approved_with_edits'"
    else:
        filter_expr = "review_status eq 'approved'"
    
    results = search_items.search(
        search_text="*",
        filter=filter_expr,
        select=[
            "id", "topic", "evidence", "stimulus", "stem",
            "option_a", "option_b", "option_c", "option_d",
            "correct_answer", "rationale",
            "quality_score", "quality_tier",
            "was_edited", "edit_summary",
            "reviewed_at", "reviewed_by"
        ],
        order_by=["reviewed_at desc"],
        top=limit
    )
    
    return [dict(r) for r in results]


def get_rejection_patterns(topic: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retrieve rejected items with explanations to identify common failure patterns.
    Useful for analytics and improving generation quality.
    
    Args:
        topic: Optional topic filter
        limit: Maximum number of items to return
    
    Returns list of rejected items with review explanations
    """
    filter_expr = "review_status eq 'rejected'"
    if topic:
        filter_expr += f" and topic eq '{topic}'"
    
    results = search_items.search(
        search_text="*",
        filter=filter_expr,
        select=[
            "id", "topic", "evidence", "stimulus", "stem",
            "quality_score", "quality_tier", "quality_summary",
            "review_decision", "review_explanation",
            "generation_batch_id", "similarity_at_generation",
            "reviewed_at", "reviewed_by"
        ],
        order_by=["reviewed_at desc"],
        top=limit
    )
    
    return [dict(r) for r in results]


def get_review_analytics() -> Dict[str, Any]:
    """
    Get summary analytics on review workflow status.
    Useful for monitoring review progress and quality trends.
    
    Returns dict with counts by review_status, quality metrics, and edit rates
    """
    # Get counts by review status
    status_counts = {}
    for status in ["pending_review", "approved", "approved_with_edits", "rejected", "gold_standard"]:
        results = search_items.search(
            search_text="*",
            filter=f"review_status eq '{status}'",
            select=["id"],
            top=0,  # Only need count
            include_total_count=True
        )
        status_counts[status] = results.get_count()
    
    # Get edit rate (approved_with_edits / total approved)
    total_approved = status_counts["approved"] + status_counts["approved_with_edits"]
    edit_rate = (status_counts["approved_with_edits"] / total_approved * 100) if total_approved > 0 else 0
    
    # Get average quality score by review status
    quality_by_status = {}
    for status in ["approved", "approved_with_edits", "rejected"]:
        results = search_items.search(
            search_text="*",
            filter=f"review_status eq '{status}'",
            select=["quality_score"],
            top=1000  # Sample size
        )
        scores = [r.get("quality_score", 0) for r in results if r.get("quality_score")]
        quality_by_status[status] = sum(scores) / len(scores) if scores else 0
    
    return {
        "status_counts": status_counts,
        "total_reviewed": status_counts["approved"] + status_counts["approved_with_edits"] + status_counts["rejected"],
        "pending_count": status_counts["pending_review"],
        "approval_rate": (total_approved / (total_approved + status_counts["rejected"]) * 100) if (total_approved + status_counts["rejected"]) > 0 else 0,
        "edit_rate": edit_rate,
        "avg_quality_by_status": quality_by_status,
    }


# Need json import for upload functions
import json