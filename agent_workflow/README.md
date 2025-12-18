# JD-Next Exam Generation - Agent Framework Workflow

Multi-agent system for JD-Next exam item generation with human-in-the-loop review, quality scoring, and approval workflow using Microsoft Agent Framework.

## Architecture

### Agents

- **Generator Agent**: Generates exam items with rubric and similarity context
- **Quality Scorer Agent**: Evaluates items across 8 quality dimensions
- **Post-Processor Agent**: Formats and validates item structure
- **Review Coordinator Agent**: Manages human review workflow (pause/resume)
- **Analytics Agent**: Tracks metrics, patterns, and performance

### Workflow Pattern

HandoffBuilder with human-in-the-loop mode:

1. Coordinator receives generation request
2. Generator creates item → Post-Processor validates
3. Quality Scorer evaluates → Routes based on quality
4. Review Coordinator pauses for human approval
5. Analytics aggregates results

## Setup

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

   Note: `agent-framework-azure-ai` requires `--pre` flag during preview

2. **Configure environment** (`.env` in root):

   ```
   AZURE_OPENAI_ENDPOINT=...
   AZURE_OPENAI_KEY=...
   AZURE_SEARCH_ENDPOINT=...
   AZURE_SEARCH_KEY=...
   ```

3. **Run workflow**:
   ```bash
   python workflows/exam_generation_workflow.py --topic "TP.2" --count 5
   ```

## Testing with DevUI

The Agent Framework includes a built-in DevUI for testing workflows interactively:

### Option 1: CLI Mode (Simple)

```bash
python tests/test_workflow_cli.py
```

- Interactive command-line interface
- Displays items awaiting review
- Collects human decisions (approve/reject/edit)
- Shows workflow progress

### Option 2: Web DevUI (Recommended)

```bash
# Install Agent Framework DevUI (if not included)
pip install agent-framework-devui

# Start DevUI server
python tests/devui_server.py
```

- Open browser to `http://localhost:5000`
- Visual workflow graph with agent states
- Review pending items in web interface
- Real-time checkpoint inspection
- Event stream visualization

### Option 3: Azure Functions + Durable Orchestration (Production)

For production deployment with scalable human-in-the-loop:

- Deploy to Azure Functions
- Use Durable Orchestration for pause/resume
- Review UI calls HTTP endpoints to submit approvals
- See `workflows/azure_functions_deployment.py`

## Project Structure

```
agent_workflow/
├── agents/              # Agent definitions with instructions
│   ├── generator_agent.py
│   ├── quality_scorer_agent.py
│   ├── post_processor_agent.py
│   ├── review_coordinator_agent.py
│   └── analytics_agent.py
├── tools/               # @ai_function tool wrappers
│   ├── generation_tools.py
│   ├── scoring_tools.py
│   ├── review_tools.py
│   └── analytics_tools.py
├── workflows/           # Workflow orchestration
│   ├── exam_generation_workflow.py
│   └── handoff_builder.py
├── config/              # Configuration and prompts
│   └── agent_config.yaml
└── tests/               # Testing interfaces
    ├── test_workflow_cli.py
    └── devui_server.py
```

## Key Concepts

### Checkpointing

- Workflow automatically saves state at pause points
- Resume with `workflow.run_stream(checkpoint_id=...)`
- Human responses applied via `workflow.send_responses_streaming(responses)`

### Human-in-the-Loop

- Review Coordinator emits `ctx.request_info()` → workflow pauses
- Azure Search stores items with `review_status="pending_review"`
- Human reviews in UI, submits decision
- Workflow resumes with approval/rejection/edits

### Quality Gate

- Auto-upload only items meeting threshold (--upload-quality-threshold)
- Low-quality items trigger retry with diversity enforcement
- Max 3 generation attempts per item

## Next Steps

1. Implement tools with @ai_function decorators
2. Define agent instructions and tool assignments
3. Build HandoffBuilder workflow with checkpointing
4. Test with CLI or DevUI
5. Deploy to Azure Functions for production
