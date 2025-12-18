"""
test_workflow_cli.py

Simple CLI interface for testing the exam generation workflow with human review.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.generation_tools import generate_item_with_context, check_diversity
from tools.scoring_tools import score_item, validate_item_structure
from tools.review_tools import upload_item_for_review, fetch_pending_reviews, submit_review_decision
from tools.analytics_tools import generate_batch_report
from config.evidence_map import get_evidence_for_topic


async def generate_and_review_item(topic_code: str):
    """Generate a single item and walk through the review process."""
    
    print(f"\n{'='*60}")
    print(f"GENERATING ITEM FOR TOPIC: {topic_code}")
    print(f"{'='*60}\n")
    
    # Step 1: Get rubric context and evidence statements for the topic
    print("Step 1: Retrieving rubric context for topic...")
    from tools.generation_tools import get_rubric_context
    rubric_chunks = get_rubric_context(topic_code, f"Topic {topic_code}", k=10)
    
    # Extract evidence statements from rubric (or use default)
    evidence_statements = [f"Demonstrate understanding of {topic_code}"]
    print(f"✅ Retrieved {len(rubric_chunks)} rubric chunks")
    
    # Step 2: Generate item
    print("\nStep 2: Generating item with context...")
    item = generate_item_with_context(
        topic_code=topic_code,
        evidence_statements=evidence_statements
    )
    
    if not item:
        print("❌ Generation failed")
        return
    
    print(f"✅ Generated item: {item.get('id', 'N/A')[:8]}")
    print(f"   Stimulus: {item.get('stimulus', '')[:80]}...")
    print(f"   Stem: {item.get('stem', '')[:80]}...")
    
    # Step 2: Validate structure
    print("\nStep 2: Validating structure...")
    validation = validate_item_structure(item)
    if not validation["is_valid"]:
        print(f"❌ Validation failed:")
        for error in validation["validation_errors"]:
            print(f"   - {error}")
        return
    print("✅ Structure valid")
    
    # Step 3: Score quality
    print("\nStep 3: Scoring quality...")
    scoring_result = score_item(item)
    item.update(scoring_result)
    
    print(f"✅ Quality Score: {item['quality_score']:.2f} ({item['quality_tier']})")
    print(f"   Improvement suggestions: {len(item.get('improvement_suggestions', []))}")
    
    # Step 4: Check diversity
    print("\nStep 4: Checking diversity...")
    diversity = check_diversity(item)
    print(f"   Max similarity: {diversity['max_similarity']:.3f}")
    print(f"   {'✅ Diverse' if diversity['is_diverse'] else '⚠️  Similar to existing items'}")
    
    # Step 5: Upload for review
    print("\nStep 5: Uploading for review...")
    upload_result = upload_item_for_review(item, review_status="pending_review")
    if upload_result["status"] == "success":
        print(f"✅ {upload_result['message']}")
    else:
        print(f"❌ {upload_result['message']}")
        return
    
    # Step 6: Simulate human review
    print(f"\n{'='*60}")
    print("HUMAN REVIEW REQUIRED")
    print(f"{'='*60}\n")
    
    print(f"Item ID: {item['id']}")
    print(f"Topic: {item['topic']}")
    print(f"Quality: {item['quality_score']:.2f} ({item['quality_tier']})")
    print(f"\nStimulus:\n{item.get('stimulus', 'N/A')}\n")
    print(f"Stem:\n{item.get('stem', 'N/A')}\n")
    print(f"Options:")
    for key, value in item.get('options', {}).items():
        marker = " ✓" if key == item.get('correct_answer') else ""
        print(f"  {key}. {value}{marker}")
    print(f"\nRationale:\n{item.get('rationale', 'N/A')}\n")
    
    # Get human decision
    decision = input("Review decision (approve/edit/reject): ").strip().lower()
    explanation = input("Explanation: ").strip()
    reviewer = input("Your email: ").strip()
    
    # Submit decision
    review_result = submit_review_decision(
        item_id=item['id'],
        decision=decision if decision in ["approved", "rejected"] else "approved_with_edits",
        explanation=explanation,
        reviewed_by=reviewer,
        edited_fields=None  # TODO: Capture edits
    )
    
    print(f"\n✅ {review_result['message']}")
    return item


async def batch_review_interface():
    """Interactive interface for reviewing pending items."""
    
    print(f"\n{'='*60}")
    print("PENDING REVIEW QUEUE")
    print(f"{'='*60}\n")
    
    # Fetch pending items
    pending = fetch_pending_reviews(limit=10)
    
    if not pending:
        print("No items pending review")
        return
    
    print(f"Found {len(pending)} items awaiting review:\n")
    
    for i, item in enumerate(pending, 1):
        print(f"{i}. {item.get('topic', 'N/A')} | Score: {item.get('quality_score', 0):.2f} | ID: {item.get('id', 'N/A')[:8]}")
    
    # Select item to review
    selection = input(f"\nSelect item to review (1-{len(pending)}) or 'q' to quit: ").strip()
    
    if selection.lower() == 'q':
        return
    
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(pending):
            item = pending[idx]
            
            # Display full item
            print(f"\n{'='*60}")
            print(f"REVIEWING ITEM {idx + 1}")
            print(f"{'='*60}\n")
            print(f"ID: {item['id']}")
            print(f"Topic: {item['topic']}")
            print(f"Quality: {item.get('quality_score', 0):.2f} ({item.get('quality_tier', 'N/A')})")
            print(f"\nStimulus:\n{item.get('stimulus', 'N/A')}\n")
            print(f"Stem:\n{item.get('stem', 'N/A')}\n")
            print(f"Options:")
            for key, value in item.get('options', {}).items():
                marker = " ✓" if key == item.get('correct_answer') else ""
                print(f"  {key}. {value}{marker}")
            print(f"\nRationale:\n{item.get('rationale', 'N/A')}\n")
            
            # Get decision
            decision = input("Decision (approve/edit/reject): ").strip().lower()
            explanation = input("Explanation: ").strip()
            reviewer = input("Your email: ").strip()
            
            # Submit
            review_result = submit_review_decision(
                item_id=item['id'],
                decision=decision if decision in ["approved", "rejected"] else "approved_with_edits",
                explanation=explanation,
                reviewed_by=reviewer
            )
            
            print(f"\n✅ {review_result['message']}")
    except (ValueError, IndexError):
        print("Invalid selection")


async def main():
    """Main CLI interface."""
    
    print("""
╔══════════════════════════════════════════════════════════╗
║     JD-Next Exam Generation - Agent Framework CLI       ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    while True:
        print("\nOptions:")
        print("  1. Generate and review single item")
        print("  2. Review pending items")
        print("  3. View analytics")
        print("  q. Quit")
        
        choice = input("\nSelect option: ").strip().lower()
        
        if choice == 'q':
            print("Goodbye!")
            break
        elif choice == '1':
            topic = input("Topic code (e.g., TP.2): ").strip()
            await generate_and_review_item(topic)
        elif choice == '2':
            await batch_review_interface()
        elif choice == '3':
            print("\n⚠️  Analytics dashboard not yet implemented")
        else:
            print("Invalid option")


if __name__ == "__main__":
    asyncio.run(main())
