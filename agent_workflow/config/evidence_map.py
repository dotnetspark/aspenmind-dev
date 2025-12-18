"""
Evidence Statements Mapping

Static mapping from evidence codes to full text statements.
This is the authoritative source for JD-Next evidence statements.

Usage:
    from config.evidence_map import EVIDENCE_MAP, get_evidence_for_topic
    
    evidence = get_evidence_for_topic("TP.2")
    # Returns all evidence statements for topic 2 (consideration)
"""

from typing import List

# Authoritative mapping of evidence codes to full text
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


def get_evidence_for_topic(topic_code: str) -> List[str]:
    """
    Retrieve all evidence statements for a given topic code.
    
    Args:
        topic_code: Topic code like "TP.2" or just "2"
    
    Returns:
        List of full evidence statements (code + text) for the topic
    
    Examples:
        >>> get_evidence_for_topic("TP.2")
        ['2.a: Apply the legal test for consideration...', '2.b: Understand what is meant...', ...]
    """
    # Extract numeric topic from various formats: "TP.2", "2"
    topic_suffix = None
    
    if topic_code.startswith("TP."):
        # Format: "TP.2" -> "2"
        topic_suffix = topic_code.split(".")[-1]
    elif "." in topic_code:
        # Format: fallback for dotted codes -> extract last part
        parts = topic_code.split(".")
        if len(parts) >= 2:
            topic_suffix = parts[1].lstrip("0")  # Remove leading zeros
    else:
        # Format: "2" -> "2"
        topic_suffix = topic_code
    
    if not topic_suffix:
        return [f"Evidence for topic {topic_code}"]
    
    # Find all matching evidence statements
    matching = [
        f"{code}: {statement}"
        for code, statement in EVIDENCE_MAP.items()
        if code.startswith(f"{topic_suffix}.")
    ]
    
    # Fallback if no matches found
    if not matching:
        return [f"Evidence for topic {topic_code}"]
    
    return matching


def get_evidence_codes_for_topic(topic_code: str) -> List[str]:
    """
    Retrieve just the evidence codes (without full text) for a topic.
    
    Args:
        topic_code: Topic code like "TP.2" or "2"
    
    Returns:
        List of evidence codes (e.g., ["2.a", "2.b", "2.c", ...])
    """
    # Extract numeric topic
    topic_suffix = None
    
    if topic_code.startswith("TP."):
        topic_suffix = topic_code.split(".")[-1]
    elif "." in topic_code:
        parts = topic_code.split(".")
        if len(parts) >= 2:
            topic_suffix = parts[1].lstrip("0")
    else:
        topic_suffix = topic_code
    
    if not topic_suffix:
        return []
    
    return [
        code for code in EVIDENCE_MAP.keys()
        if code.startswith(f"{topic_suffix}.")
    ]
