# Evidence Statement Integration

## Overview

The static evidence statements mapping from `generate_items_v2.py` has been integrated into the agent workflow. Evidence statements are now automatically retrieved based on topic code.

## What Was Added

### 1. **config/evidence_map.py** (New Module)

Contains the authoritative `EVIDENCE_MAP` with all evidence statements:

- `EVIDENCE_MAP`: Dict mapping evidence codes (e.g., "2.a", "2.b") to full text
- `get_evidence_for_topic(topic_code)`: Retrieves all evidence statements for a topic
- `get_evidence_codes_for_topic(topic_code)`: Returns just the codes

**Supports topic code formats:**

- `"TP.2"` → extracts "2" → returns all "2.x" evidence statements
- `"2"` → returns all "2.x" evidence statements

### 2. **config/**init**.py** (New Module)

Exports the evidence mapping functions for easy import.

### 3. **tools/generation_tools.py** (Updated)

Added new agent-accessible function:

- `@ai_function get_evidence_for_topic_code(topic_code)`: Returns evidence statements from static mapping
- Imported `get_evidence_for_topic` from config module

### 4. **agents/generator_agent.py** (Updated)

- Added `get_evidence_for_topic_code` to tool list
- Updated instructions to clarify evidence retrieval workflow:
  1. Call `get_evidence_for_topic_code("TP.2")` first
  2. Use returned evidence statements for generation
  3. No need to manually pass evidence statements

### 5. **tests/test_workflow_cli.py** (Updated)

- Imported `get_evidence_for_topic` from config module
- CLI now displays actual evidence statements instead of placeholder
- Shows all evidence statements for the topic before generation

## Evidence Map Contents

The map currently includes evidence statements for topics 1-9:

### Topic 2 (Consideration) - Relevant for "TP.2"

- `2.a`: Apply the legal test for consideration, including both elements of legal value and bargained-for-exchange.
- `2.b`: Understand what is meant by 'legal value' and 'bargained-for-exchange.'
- `2.c`: Identify the legal detriment to the promisee and/or legal benefit to the promisor in a given fact pattern.
- `2.d`: Identify what is meant by the term 'consideration' in the context of contracts and gifts.
- `2.e`: Understand the concept of adequacy of consideration and the principle of 'freedom of contract.'
- `2.f`: Understand why courts, as a general rule, do not inquire into the adequacy of consideration.

### Other Topics

- Topic 1: Expectation damages (1.a - 1.c)
- Topic 3: Gratuitous promises (3.a - 3.b)
- Topic 4: Past consideration (4.a - 4.b)
- Topic 5: Illusory promises (5.a - 5.b)
- Topic 6: Objective theory (6.a - 6.b)
- Topic 7: Valid offer (7.a - 7.b)
- Topic 8: Valid acceptance (8.a - 8.b)
- Topic 9: Promissory estoppel (9.a - 9.b)

## Usage in DevUI

When testing with DevUI, you only need to specify the topic code:

```
Generate 3 items for topic TP.2
```

The workflow will:

1. Extract topic number "2" from "TP.2"
2. Retrieve all evidence statements for topic 2 (2.a through 2.f)
3. Generate items aligned to those evidence statements
4. Continue through scoring, review, and analytics

## Usage in Code

```python
from config.evidence_map import get_evidence_for_topic

# Get evidence statements for topic TP.2
evidence = get_evidence_for_topic("TP.2")
# Returns:
# [
#   "2.a: Apply the legal test for consideration...",
#   "2.b: Understand what is meant by 'legal value'...",
#   ...
# ]
```

## Next Steps

You're now ready to test the complete workflow with DevUI:

```powershell
cd agent_workflow
python -m agent_framework.devui --workflow workflows/exam_generation_workflow.py
```

Then send: **"Generate 3 items for topic TP.2"**

The Generator Agent will automatically retrieve the 6 evidence statements for consideration (2.a - 2.f) and generate items aligned to them.
