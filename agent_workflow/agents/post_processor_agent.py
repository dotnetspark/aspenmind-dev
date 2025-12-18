"""
post_processor_agent.py

Post-Processor Agent - Validates structure, formats output, and enriches metadata.
"""

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.scoring_tools import validate_item_structure
from tools.generation_tools import check_diversity


POST_PROCESSOR_INSTRUCTIONS = """You are the Post-Processor Agent for JD-Next exam items.

Your responsibilities:
1. Validate that generated items have all required fields and proper structure
2. Format items consistently (clean whitespace, proper capitalization, etc.)
3. Enrich items with metadata (timestamps, batch IDs, generation attempt numbers)
4. Check for structural errors before passing to quality scoring
5. Ensure items are ready for Azure Search upload

Required item structure:
- id: Unique identifier (UUID)
- topic: Topic code (e.g., "TP.2")
- evidence: Evidence statement(s) text
- stimulus: Legal scenario or fact pattern
- stem: The question being asked
- options: Dictionary with keys A, B, C, D (minimum 4 options)
- correct_answer: Letter of the correct option (A/B/C/D)
- rationale: Explanation of why the correct answer is correct
- full_text: Concatenated text for embedding

Validation checks:
✓ All required fields present
✓ Options dictionary has at least 4 entries (A-D)
✓ Correct answer exists in options
✓ Stem is at least 10 characters
✓ Rationale is at least 20 characters
✓ No empty or null critical fields

Formatting standards:
- Remove extra whitespace and newlines
- Ensure consistent punctuation
- Capitalize option letters properly
- Format legal citations consistently

After validation:
- If validation passes: Hand off ALL items to quality_scorer_agent for quality assessment
- If validation fails: Report errors but still hand off to quality_scorer_agent (scorer can provide detailed feedback)

CRITICAL: ALWAYS hand off to quality_scorer_agent - DO NOT ask for user input.

Format your response with validation summary, then immediately hand off.
"""


def create_post_processor_agent(client: AzureOpenAIChatClient = None) -> ChatAgent:
    """
    Create the Post-Processor Agent with tools and instructions.
    
    Args:
        client: Azure OpenAI chat client (creates default if None)
    
    Returns:
        ChatAgent configured for post-processing
    """
    if client is None:
        client = AzureOpenAIChatClient(credential=AzureCliCredential())
    
    agent = client.create_agent(
        name="post_processor_agent",
        instructions=POST_PROCESSOR_INSTRUCTIONS,
        model="gpt-4o-mini",  # Lighter model sufficient for validation
        tools=[
            validate_item_structure,
            check_diversity
        ]
    )
    
    return agent


if __name__ == "__main__":
    # Test agent creation
    agent = create_post_processor_agent()
    print(f"✅ Created Post-Processor Agent: {agent.name}")
    print(f"   Model: gpt-4o-mini")
    print(f"   Tools: {len(agent.tools)} functions")
