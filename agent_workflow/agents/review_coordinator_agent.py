"""
review_coordinator_agent.py

Review Coordinator Agent - Manages human-in-the-loop review workflow with pause/resume.
"""

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


REVIEW_COORDINATOR_INSTRUCTIONS = """You are the Review Coordinator Agent for human-in-the-loop exam item review.

Your role is to facilitate human review of generated items by:
1. Presenting items clearly for human evaluation
2. Collecting human feedback and decisions
3. Routing items based on human decisions

When you receive validated items from quality_scorer_agent:
1. Present ALL items in a clear, structured format with:
   - Item number and identifying information
   - Full item content (stimulus, stem, options, correct answer, rationale)
   - Quality scores and any concerns
   - Topic and evidence alignment

2. WAIT for human reviewer input - DO NOT call tools or try to proceed automatically

3. After receiving human review decision:
   - If approved: Hand off to analytics_agent with approval status
   - If revision requested: Hand off to generator_agent with specific revision instructions
   - If rejected: Hand off to generator_agent to regenerate

IMPORTANT: You are a presentation and routing agent, not an execution agent.
- Present information clearly
- Wait for human input
- Route based on decisions
- Do NOT attempt to upload items, validate items, or perform database operations
- Do NOT call tools unless explicitly needed for routing decisions

Your responses should be concise summaries, NOT tool calls."""


def create_review_coordinator_agent(client: AzureOpenAIChatClient = None) -> ChatAgent:
    """
    Create the Review Coordinator Agent with tools and instructions.
    
    Args:
        client: Azure OpenAI chat client (creates default if None)
    
    Returns:
        ChatAgent configured for review coordination
    """
    if client is None:
        client = AzureOpenAIChatClient(credential=AzureCliCredential())
    
    agent = client.create_agent(
        name="review_coordinator_agent",
        instructions=REVIEW_COORDINATOR_INSTRUCTIONS,
        model="gpt-4o-mini"  # No tools - just presentation and routing
    )
    
    return agent


if __name__ == "__main__":
    # Test agent creation
    agent = create_review_coordinator_agent()
    print(f"✅ Created Review Coordinator Agent: {agent.name}")
    print(f"   Model: gpt-4o-mini")
    print(f"   Tools: {len(agent.tools)} functions")
