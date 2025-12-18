# Agent Framework Project - Setup Guide

## Quick Start

### 1. Install Dependencies

From the `agent_workflow` directory:

```powershell
# Install Microsoft Agent Framework (PREVIEW - requires --pre flag)
pip install --pre agent-framework-azure-ai

# Install other dependencies
pip install -r requirements.txt
```

**Note**: During preview, `agent-framework-azure-ai` requires the `--pre` flag.

### 2. Test the CLI

Run the interactive CLI to test the workflow without the full agent orchestration:

```powershell
cd tests
python test_workflow_cli.py
```

This provides a simple menu-driven interface to:

- Generate single items with quality scoring
- Review pending items from the queue
- Submit approval/rejection decisions

### 3. Test with Full Agent Workflow (Coming Soon)

Once agent definitions are complete:

```powershell
python workflows/exam_generation_workflow.py --topic "TP.2" --count 5
```

## Testing with DevUI

The Microsoft Agent Framework includes built-in developer tools for testing workflows.

### Option 1: CLI Testing (Current)

The `test_workflow_cli.py` provides an interactive command-line interface:

```powershell
cd agent_workflow/tests
python test_workflow_cli.py
```

**Features**:

- Generate items with live quality scoring
- Interactive review interface
- Submit decisions (approve/reject/edit)
- View pending review queue

**Workflow**:

1. Select "Generate and review single item"
2. Enter topic code (e.g., `TP.2`)
3. Enter evidence statement
4. System generates → validates → scores → uploads
5. Human reviews and approves/rejects
6. Decision recorded in Azure Search

### Option 2: Web DevUI (Future)

Microsoft Agent Framework includes a web-based DevUI for visual workflow testing:

```powershell
# Install DevUI extension (when available)
pip install agent-framework-devui

# Start DevUI server
python -m agent_framework.devui --workflow workflows/exam_generation_workflow.py
```

**Features** (based on framework documentation):

- Visual workflow graph showing agent states
- Live event stream visualization
- Checkpoint inspection and resume
- Interactive human-in-the-loop prompts
- Real-time metrics dashboard

**Access**: `http://localhost:5000`

### Option 3: Azure Functions Deployment (Production)

For production deployment with scalable HITL:

```powershell
# Deploy to Azure Functions with Durable Orchestration
func azure functionapp publish <your-function-app>
```

**Human Review Flow**:

1. Workflow starts → generates items → pauses at Review Coordinator
2. `POST /api/review/submit` → Human reviews in custom UI
3. UI submits decision → raises event to orchestration
4. Workflow resumes from checkpoint → continues to Analytics

See `workflows/azure_functions_deployment.py` for deployment template.

## Current Project Status

✅ **Completed**:

- Project structure with agents/, tools/, workflows/, tests/
- 20+ @ai_function tools (generation, scoring, review, analytics)
- CLI test interface for interactive testing
- Requirements and documentation

🚧 **In Progress**:

- Agent definitions with instructions and tool assignments

⏭️ **Next Steps**:

1. Define 5 specialized agents (Generator, Scorer, Post-Processor, Review Coordinator, Analytics)
2. Build HandoffBuilder workflow with human-in-the-loop mode
3. Add checkpointing for pause/resume
4. Test end-to-end with CLI
5. Deploy to Azure Functions (optional)

## DevUI Testing Recommendations

**For Development** (Current):

- Use `test_workflow_cli.py` for quick iteration
- Test individual tools and review workflow
- Validate quality scoring and diversity checking

**For Demo/Testing** (Future):

- Use web DevUI to visualize workflow graph
- Show stakeholders the human-in-the-loop pause points
- Inspect checkpoints and event streams

**For Production**:

- Deploy to Azure Functions with Durable Orchestration
- Build custom review UI (web app)
- Integrate with authentication and role-based access

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError` for `agent_framework`:

```powershell
pip install --pre agent-framework-azure-ai
```

### Path Issues

The tools import from parent directory (`../../`). Ensure you run from:

- `agent_workflow/tests/` for CLI
- `agent_workflow/workflows/` for workflows

### Azure Credentials

Ensure `.env` in root directory has:

```
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_KEY=...
AZURE_SEARCH_ENDPOINT=...
AZURE_SEARCH_KEY=...
```

## Next: Implement Agents

See `agents/` directory for agent definitions:

- `generator_agent.py` - Item generation with context
- `quality_scorer_agent.py` - Quality evaluation
- `post_processor_agent.py` - Validation and formatting
- `review_coordinator_agent.py` - Human review orchestration
- `analytics_agent.py` - Metrics and reporting
