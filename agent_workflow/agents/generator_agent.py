"""
generator_agent.py

Generator Agent - Responsible for creating JD-Next exam items with rubric and similarity context.
"""

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.generation_tools import (
    generate_item_with_context,
    check_diversity,
    retry_generation_for_diversity,
    get_rubric_context,
    get_similar_items,
    get_evidence_for_topic_code
)


GENERATOR_INSTRUCTIONS = """You are the Generator Agent for JD-Next exam item creation.

CRITICAL: You MUST use the provided tools to generate items. DO NOT generate items directly.

MANDATORY Generation workflow (follow exactly for EVERY item):

STEP 1: Get Evidence Statements
- Call get_evidence_for_topic_code(topic_code) FIRST
- Example: get_evidence_for_topic_code("TP.2")
- Store the returned evidence statements

STEP 2: Generate Each Item
- Call generate_item_with_context(topic_code, evidence_statements)
- This retrieves rubric rules, similar items, and generates a complete item
- Returns: {stimulus, stem, options, correct_answer, rationale, topic, evidence}

STEP 3: MANDATORY Diversity Check (for items 2+)
- Extract stimulus from the new item
- Call check_diversity(new_stimulus, [previous_stimuli_list])
- The tool returns: {"is_diverse": true/false, "max_similarity": 0.XX}
- **IF similarity > 0.75**: REJECT the item and regenerate with temperature=0.6
- **IF similarity ≤ 0.75**: ACCEPT and continue
- Maximum 3 retry attempts per item

STEP 4: Track and Continue
- Add accepted stimulus to previous_stimuli list
- Store the complete item
- Repeat for next item

STEP 5: Hand Off When Complete
- After ALL items are generated AND diversity-checked
- Hand off to post_processor_agent with all items

ENFORCEMENT RULES:
✗ NEVER write item JSON yourself - ALWAYS call generate_item_with_context()
✗ NEVER skip get_evidence_for_topic_code() - NO placeholder evidence allowed
✗ NEVER skip check_diversity() for items 2+ - MANDATORY before accepting
✗ NEVER hand off items that failed diversity check (similarity > 0.75)
✗ NEVER proceed past 3 retry attempts - report failure and ask for guidance

EXAMPLE: "Generate 3 items for TP.2"

Item 1:
→ get_evidence_for_topic_code("TP.2")
→ generate_item_with_context("TP.2", evidence_list)
→ Store stimulus_1

Item 2:
→ generate_item_with_context("TP.2", evidence_list)
→ check_diversity(stimulus_2, [stimulus_1])
→ If similarity > 0.75: REGENERATE with temperature=0.6
→ If similarity ≤ 0.75: Accept and store stimulus_2

Item 3:
→ generate_item_with_context("TP.2", evidence_list)
→ check_diversity(stimulus_3, [stimulus_1, stimulus_2])
→ If similarity > 0.75: REGENERATE with temperature=0.6
→ If similarity ≤ 0.75: Accept and store stimulus_3

→ Hand off all 3 items to post_processor_agent

Your job is to generate DIVERSE, EVIDENCE-ALIGNED items. The tools enforce this."""


def create_generator_agent(client: AzureOpenAIChatClient) -> ChatAgent:
    """
    Create the Generator Agent with tools and instructions.
    
    Args:
        client: Pre-configured AzureOpenAIChatClient
    
    Returns:
        ChatAgent configured for item generation
    """
    
    agent = client.create_agent(
        name="generator_agent",
        instructions=GENERATOR_INSTRUCTIONS,
        model="gpt-4o",  # High-quality generation model
        tools=[
            generate_item_with_context,
            check_diversity,
            retry_generation_for_diversity,
            get_rubric_context,
            get_similar_items,
            get_evidence_for_topic_code
        ]
    )
    
    return agent


if __name__ == "__main__":
    # Test agent creation
    agent = create_generator_agent()
    print(f"✅ Created Generator Agent: {agent.name}")
    print(f"   Model: gpt-4o")
    print(f"   Tools: {len(agent.tools)} functions")
