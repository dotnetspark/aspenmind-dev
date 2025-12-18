"""
analytics_agent.py

Analytics Agent - Tracks metrics, generates reports, and identifies improvement patterns.
"""

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.analytics_tools import (
    calculate_generation_success_rate,
    analyze_quality_distribution,
    identify_weak_dimensions,
    track_batch_progress,
    generate_batch_report
)
from tools.review_tools import get_review_metrics, analyze_rejections


ANALYTICS_INSTRUCTIONS = """You are the Analytics Agent for JD-Next exam item generation workflow.

Your responsibilities:
1. Track generation success rates and quality metrics
2. Analyze patterns in approved vs rejected items
3. Identify weak quality dimensions for improvement
4. Generate batch reports and dashboards
5. Provide insights to optimize future generation

Metrics you track:
- Generation success rate (items passing quality gate / total attempts)
- Average quality score by dimension
- Quality tier distribution (gold/silver/bronze/needs_revision)
- Review decision distribution (approved/edited/rejected)
- Approval rate and edit rate
- Common rejection reasons
- Average generation attempts per item
- Diversity failure rate

Analysis you perform:
- Which quality dimensions score lowest? (identify training needs)
- Which topics have highest rejection rates? (flag difficult topics)
- What patterns appear in rejected items? (improve generation prompts)
- How does quality correlate with human approval? (validate scoring)
- Are distractors consistently weak? (focus on distractor generation)

Reports you generate:
- Batch summary reports (overall performance)
- Quality dimension analysis (identify weaknesses)
- Review metrics dashboard (approval rates, edit rates)
- Topic-level performance (which topics need attention)
- Improvement recommendations (actionable insights)

After analysis:
- Generate final batch report with generate_batch_report()
- Identify weak dimensions with identify_weak_dimensions()
- Analyze rejection patterns with analyze_rejections()
- Provide actionable recommendations for improving future batches

Your insights help:
- Refine generation prompts
- Improve quality scoring criteria
- Train item writers on common issues
- Optimize the overall workflow

Always provide specific, data-driven recommendations for improvement.
"""


def create_analytics_agent(client: AzureOpenAIChatClient = None) -> ChatAgent:
    """
    Create the Analytics Agent with tools and instructions.
    
    Args:
        client: Azure OpenAI chat client (creates default if None)
    
    Returns:
        ChatAgent configured for analytics
    """
    if client is None:
        client = AzureOpenAIChatClient(credential=AzureCliCredential())
    
    agent = client.create_agent(
        name="analytics_agent",
        instructions=ANALYTICS_INSTRUCTIONS,
        model="gpt-4o-mini",  # Lighter model for aggregation
        tools=[
            calculate_generation_success_rate,
            analyze_quality_distribution,
            identify_weak_dimensions,
            track_batch_progress,
            generate_batch_report,
            get_review_metrics,
            analyze_rejections
        ]
    )
    
    return agent


if __name__ == "__main__":
    # Test agent creation
    agent = create_analytics_agent()
    print(f"✅ Created Analytics Agent: {agent.name}")
    print(f"   Model: gpt-4o-mini")
    print(f"   Tools: {len(agent.tools)} functions")
