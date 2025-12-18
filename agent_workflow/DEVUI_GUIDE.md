# Running with DevUI - Step-by-Step Guide

## Prerequisites

1. **Ensure dependencies are installed**:

   ```powershell
   cd C:\Users\ylrre\source\repos\aspenmind-dev\agent_workflow
   pip install --pre agent-framework-azure-ai
   pip install -r requirements.txt
   ```

2. **Configure Azure credentials** (if not already done):
   ```powershell
   az login
   ```

## Option 1: Using Agent Framework DevUI (Recommended)

The Microsoft Agent Framework includes a web-based DevUI for interactive workflow testing.

### Step 1: Start the DevUI Server

```powershell
cd C:\Users\ylrre\source\repos\aspenmind-dev\agent_workflow

# Launch DevUI pointing to your workflow
python -m agent_framework.devui --workflow workflows/exam_generation_workflow.py
```

If `agent_framework.devui` module is not available, check the framework version:

```powershell
pip show agent-framework-azure-ai
```

### Step 2: Open DevUI in Browser

The DevUI will start a local web server (typically `http://localhost:5000`). Open your browser to:

```
http://localhost:5000
```

### Step 3: Start Workflow in DevUI

In the DevUI interface:

1. **Load Workflow**: Click "Load Workflow" → select `exam_generation_workflow.py`
2. **Start Session**: Click "New Session"
3. **Send Message**: Enter your generation request:
   ```
   Generate 3 JD-Next exam items for topic TP.2 with evidence statement:
   "Analyze legal scenarios involving contract law principles"
   ```

### Step 4: Monitor Workflow

DevUI shows:

- **Workflow Graph**: Visual representation of agent handoffs
- **Event Stream**: Live updates as agents process
- **Current State**: Which agent is active
- **Pending Requests**: When Review Coordinator pauses for human input

### Step 5: Human Review (The HITL Pause Point)

When the workflow reaches Review Coordinator:

1. **DevUI displays**: "Human input required" notification
2. **Review Panel opens**: Shows item details

   - Stimulus (legal scenario)
   - Stem (question)
   - Options A-D with correct answer marked
   - Rationale
   - Quality score and tier
   - Improvement suggestions

3. **Make Decision**:

   - Click "Approve" → Item goes to Analytics
   - Click "Edit" → Make changes, then approve
   - Click "Reject" → Provide explanation, item retries generation

4. **Submit**: Click "Submit Review" → Workflow resumes

### Step 6: View Results

After all items are reviewed:

- Analytics Agent generates final batch report
- DevUI displays completion status
- Checkpoints saved to `workflows/checkpoints/`

## Option 2: Using CLI Test Interface (Simpler)

If DevUI is not available, use the CLI interface:

```powershell
cd C:\Users\ylrre\source\repos\aspenmind-dev\agent_workflow\tests
python test_workflow_cli.py
```

Then select:

1. "Generate and review single item"
2. Enter topic: `TP.2`
3. Enter evidence statement
4. Review in terminal and approve/reject

## Option 3: Programmatic Workflow Execution

Run the workflow directly from Python:

```powershell
cd C:\Users\ylrre\source\repos\aspenmind-dev\agent_workflow\workflows
python exam_generation_workflow.py --topic TP.2 --count 3 --evidence "Analyze contract law"
```

**Note**: This runs without visual UI. Human review pauses will require implementing a custom interface.

## DevUI Features You'll See

### 1. Workflow Graph

Visual diagram showing:

- All 6 agents (Coordinator, Generator, Post-Processor, Quality Scorer, Review Coordinator, Analytics)
- Handoff paths (arrows between agents)
- Current active agent (highlighted)
- Completed handoffs (green checkmarks)

### 2. Event Stream

Live log of workflow events:

```
[AgentExecutorRequest] Coordinator → Generator
[AgentExecutorResponse] Generator: Item generated with ID xyz
[AgentExecutorRequest] Generator → Post-Processor
[AgentExecutorResponse] Post-Processor: Validation passed
[AgentExecutorRequest] Post-Processor → Quality Scorer
[AgentExecutorResponse] Quality Scorer: Score 4.2 (silver tier)
[RequestInfoEvent] Review Coordinator: Human review required
⏸️  WORKFLOW PAUSED - Awaiting human input
```

### 3. Checkpoint Inspector

View saved checkpoints:

- Checkpoint ID
- Timestamp
- Iteration count
- Pending requests (review items waiting for human)
- Resume capability (click to resume from any checkpoint)

### 4. Human Review Panel

Interactive form showing:

- **Item Content**: Full display of stimulus, stem, options, rationale
- **Quality Context**: Score, tier, suggestions
- **Decision Buttons**: Approve / Edit / Reject
- **Explanation Field**: Text box for human comments
- **Submit Button**: Resumes workflow with decision

### 5. Analytics Dashboard

After completion:

- Items generated: 3
- Average quality: 4.1
- Tier distribution: 2 silver, 1 gold
- Approval rate: 100%
- Batch report (text summary)

## Troubleshooting

### DevUI Module Not Found

If you see `ModuleNotFoundError: No module named 'agent_framework.devui'`:

The DevUI may be a separate package or feature. Try:

```powershell
pip install agent-framework-devui
```

Or check Microsoft Agent Framework documentation for the correct DevUI launch command.

### Alternative: Use Jupyter Notebook

Create a notebook to run the workflow interactively:

```python
# In Jupyter cell 1
from agent_framework.workflows.exam_generation_workflow import create_exam_generation_workflow

workflow = create_exam_generation_workflow()

# In Jupyter cell 2
async for event in workflow.run_stream(message="Generate 1 item for TP.2"):
    print(event)
```

### Checkpoint Location

Checkpoints are saved to:

```
C:\Users\ylrre\source\repos\aspenmind-dev\agent_workflow\workflows\checkpoints\
```

You can inspect these JSON files to see workflow state during pauses.

## Next Steps

1. **Start with CLI**: Test basic functionality with `test_workflow_cli.py`
2. **Try DevUI**: Launch DevUI for visual workflow monitoring
3. **Generate Items**: Request generation for topic TP.2
4. **Review in DevUI**: Approve/reject items in the visual interface
5. **View Analytics**: See batch report and metrics

## Example DevUI Session

```
User: Generate 2 items for topic TP.2 about analyzing tort law scenarios

DevUI: Workflow started (session: abc-123)
       Coordinator → Generator

DevUI: Generator Agent creating item 1...
       Using rubric context: 10 chunks
       Similar items retrieved: 5
       ✓ Item generated

DevUI: Post-Processor validating...
       ✓ Structure valid

DevUI: Quality Scorer evaluating...
       Clarity: 4.5, Cognitive Level: 4.0, Overall: 4.2
       Tier: SILVER
       ✓ Score assigned

DevUI: Review Coordinator uploading...
       ✓ Item uploaded to Azure Search (review_status=pending_review)

⏸️  WORKFLOW PAUSED
    Human review required for item 1

[Review Panel Opens in DevUI]
    Topic: TP.2
    Quality: 4.2 (silver)

    Stimulus: [Legal scenario displayed]
    Stem: [Question displayed]
    Options: [A-D displayed with correct answer marked]
    Rationale: [Explanation displayed]

    Suggestions:
    - Consider strengthening distractor C
    - Rationale could be more concise

    [ Approve ] [ Edit ] [ Reject ]
    Explanation: _____________________
                 [ Submit Review ]

User clicks: [Approve] → Enter explanation: "Item meets standards" → [Submit]

DevUI: Review Coordinator received decision: APPROVED
       ✓ Decision recorded
       Workflow resuming...
       Review Coordinator → Analytics

[Process repeats for item 2...]

DevUI: Analytics Agent generating report...
       ✓ Batch report complete

       === Batch Report ===
       Total Items: 2
       Quality: 2 silver
       Review: 2 approved
       Success Rate: 100%

       Workflow complete! ✓
```

This is the interactive experience you'll have with DevUI for testing your multi-agent workflow with human-in-the-loop review.
