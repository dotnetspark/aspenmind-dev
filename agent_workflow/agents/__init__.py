"""
__init__.py

Agent definitions for JD-Next exam generation workflow.
"""

from .generator_agent import create_generator_agent, GENERATOR_INSTRUCTIONS
from .quality_scorer_agent import create_quality_scorer_agent, QUALITY_SCORER_INSTRUCTIONS
from .post_processor_agent import create_post_processor_agent, POST_PROCESSOR_INSTRUCTIONS
from .review_coordinator_agent import create_review_coordinator_agent, REVIEW_COORDINATOR_INSTRUCTIONS
from .analytics_agent import create_analytics_agent, ANALYTICS_INSTRUCTIONS

__all__ = [
    'create_generator_agent',
    'create_quality_scorer_agent',
    'create_post_processor_agent',
    'create_review_coordinator_agent',
    'create_analytics_agent',
    'GENERATOR_INSTRUCTIONS',
    'QUALITY_SCORER_INSTRUCTIONS',
    'POST_PROCESSOR_INSTRUCTIONS',
    'REVIEW_COORDINATOR_INSTRUCTIONS',
    'ANALYTICS_INSTRUCTIONS',
]
