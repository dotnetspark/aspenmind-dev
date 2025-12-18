"""
Configuration module for agent workflow.

Provides access to static mappings and configuration data.
"""

from .evidence_map import EVIDENCE_MAP, get_evidence_for_topic, get_evidence_codes_for_topic

__all__ = [
    "EVIDENCE_MAP",
    "get_evidence_for_topic",
    "get_evidence_codes_for_topic",
]
