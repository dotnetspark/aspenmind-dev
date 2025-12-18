"""
exam_generation_workflow.py

Main workflow orchestration using HandoffBuilder for JD-Next exam generation
with human-in-the-loop review via DevUI.
"""

import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from agent_framework import HandoffBuilder, FileCheckpointStorage
from agent_framework.azure import AzureOpenAIChatClient

import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import from retrieval.py (which already loads .env and configures clients)
from retrieval import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME
)

from agents import (
    create_generator_agent,
    create_quality_scorer_agent,
    create_post_processor_agent,
    create_review_coordinator_agent,
    create_analytics_agent
)


# Checkpoint storage directory
CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def create_exam_generation_workflow(checkpoint_storage: Optional[FileCheckpointStorage] = None):
    """
    Build the HandoffBuilder workflow for exam generation with HITL review.
    
    Returns:
        Configured workflow ready for DevUI
    """
    # Use Azure OpenAI configuration from retrieval.py (already loaded from .env)
    client = AzureOpenAIChatClient(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version="2024-02-01"  # Match retrieval.py version
    )
    
    # Create all 5 agents
    generator = create_generator_agent(client)
    post_processor = create_post_processor_agent(client)
    quality_scorer = create_quality_scorer_agent(client)
    review_coordinator = create_review_coordinator_agent(client)
    analytics = create_analytics_agent(client)
    
    # Create coordinator (lightweight orchestration agent)
    coordinator = client.create_agent(
        name="coordinator",
        instructions="""You are the Coordinator Agent for exam generation workflow.
        
Your role:
1. Receive generation requests (topic code and count)
2. Extract the exact topic code and count from user request
3. Hand off to Generator Agent with clear instructions
4. Monitor workflow progress
5. Present final results to user

When a user requests item generation:
- Parse the request to extract: topic code (e.g., "TP.2") and count (e.g., 3)
- Hand off to generator_agent with message: "Generate [count] items for topic [topic_code]"
- Example: "Generate 3 items for topic TP.2"
- The Generator Agent will use its tools to retrieve evidence and generate items
- Wait for workflow to complete
- Present final results to user

CRITICAL: Pass the exact topic code to generator_agent (e.g., "TP.2" not "consideration" or "perpetuities")

You do NOT generate items yourself - you coordinate the workflow.""",
        model="gpt-4o-mini"
    )
    
    # Build the HandoffBuilder workflow
    if checkpoint_storage is None:
        checkpoint_storage = FileCheckpointStorage(storage_path=CHECKPOINT_DIR)
    
    workflow = (
        HandoffBuilder(
            name="exam_generation_workflow",
            participants=[coordinator, generator, post_processor, quality_scorer, review_coordinator, analytics]
        )
        .set_coordinator(coordinator)
        # Main generation path
        .add_handoff(coordinator, generator)
        .add_handoff(generator, post_processor)
        .add_handoff(post_processor, quality_scorer)
        # Quality-based routing
        .add_handoff(quality_scorer, review_coordinator)  # Items ≥2.5 go to review
        .add_handoff(quality_scorer, generator)  # Items <2.5 retry generation
        # Review outcomes
        .add_handoff(review_coordinator, analytics)  # Approved items
        .add_handoff(review_coordinator, generator)  # Rejected items retry
        # Completion
        .add_handoff(analytics, coordinator)  # Final report
        .with_interaction_mode("human_in_loop")  # Enable HITL at review_coordinator
        .with_checkpointing(checkpoint_storage)
        .with_termination_condition(
            lambda conv: any("batch report" in str(msg).lower() for msg in conv[-5:])
        )
        .build()
    )
    
    return workflow


async def run_workflow_cli(topic: str, count: int = 1):
    """
    Run the workflow from command line (without DevUI).
    
    Args:
        topic: Topic code (e.g., "TP.2")
        count: Number of items to generate
    """
    workflow = create_exam_generation_workflow()
    
    batch_id = str(uuid.uuid4())[:8]
    request_message = f"""Generate {count} JD-Next exam items for:
Topic: {topic}
Batch ID: {batch_id}

Requirements:
- Retrieve rubric and evidence statements automatically for topic {topic}
- Each item must have stimulus, stem, 4 options (A-D), correct answer, and rationale
- Check diversity (max similarity 0.75)
- Score quality across 8 dimensions
- Upload items for human review with review_status="pending_review"
- Generate final batch report"""
    
    print(f"\n{'='*60}")
    print(f"Starting Exam Generation Workflow")
    print(f"Topic: {topic}")
    print(f"Count: {count}")
    print(f"Batch ID: {batch_id}")
    print(f"{'='*60}\n")
    
    # Run workflow
    async for event in workflow.run_stream(message=request_message):
        print(f"[{event.__class__.__name__}] {str(event)[:100]}")
    
    print(f"\n{'='*60}")
    print("Workflow Complete")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="JD-Next Exam Generation Workflow")
    parser.add_argument("--topic", default="TP.2", help="Topic code (e.g., TP.2)")
    parser.add_argument("--count", type=int, default=1, help="Number of items to generate")
    
    args = parser.parse_args()
    
    asyncio.run(run_workflow_cli(
        topic=args.topic,
        count=args.count
    ))
