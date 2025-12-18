# AspenMind Exam Item Generation Pipeline

This project provides a comprehensive pipeline for generating, scoring, reviewing, and managing scenario-based multiple-choice exam items for professional exams (JD-Next), using Azure OpenAI and Azure AI Search with human-in-the-loop review workflow.

## Purpose

- Automate the creation of high-quality, legally accurate exam items aligned to specific evidence statements and JD-Next rubric standards.
- Support large-scale item generation with built-in quality scoring (8 dimensions, 0-5 scale) and semantic diversity checking.
- Enable human-in-the-loop review workflow with state management for approval, editing, and rejection tracking.
- Provide analytics and feedback loops to continuously improve generation quality.
- Enable retrieval-augmented generation (RAG) using vector search over prototype items, rubric rules, and evidence statements.

## Features

### **Generation & Quality Control**

- **Multi-Stage Generation**: Generates items with comprehensive rubric context (ALL mandatory rules + semantic examples + similar items)
- **Quality Scoring**: 8-dimensional scoring system (Clarity, Cognitive Level, Evidence Alignment, Plausibility, Legal Accuracy, Scenario Quality, Rationale Quality, Overall Quality) with 4-tier classification (gold/silver/bronze/needs_revision)
- **Post-Processing Pipeline**:
  - Automatic answer shuffling (truly random A/B/C/D positions)
  - Evidence statement validation and auto-fix
  - Semantic diversity checking with retry logic (max 3 attempts when similarity > 0.75)
- **Generation Metadata**: Full traceability with batch IDs, attempt counts, and similarity scores

### **Human-in-the-Loop Review Workflow**

- **State Management**: 5 review states (`gold_standard`, `pending_review`, `approved`, `approved_with_edits`, `rejected`)
- **Edit Tracking**: Captures original versions before human edits with field-level change summaries
- **Review Analytics**: Approval rates, edit rates, rejection patterns, and quality trends by review status
- **Agent-Ready APIs**: Stateless functions designed for Microsoft Agent Framework integration

### **Vector Search & RAG**

- **Azure AI Search**: Vector search over exam items (1536-dim embeddings) and rubric rules
- **Semantic Retrieval**: Query similar items, retrieve by quality tier, and find gold standard examples
- **Comprehensive Context**: Combines mandatory rules + semantic examples + similar items for generation

### **Security & Observability**

- **Environment Variables**: All secrets managed via `.env` file (never committed)
- **Full Audit Trail**: Timestamps, reviewer IDs, quality scores, and generation metadata for every item

## Structure

- **`generate_items_v2.py`**: Main generation script with quality scoring, diversity checking, and upload capabilities
- **`retrieval.py`**: Vector search, rubric retrieval, quality-aware queries, and review management functions
- **`exam_ingestion_pipeline.ipynb`**: Index schema creation and data ingestion for exam items
- **`rubric_ingestion_pipeline.ipynb`**: Index creation and ingestion for JD-Next rubric rules
- **`maintenance.ipynb`**: Utilities for index management, evidence inspection, and data cleanup
- **`dataset/`**: Source CSV files with gold standard exam items and metadata
- **`output/`**: Generated exam items in JSONL format
- **`item-writing/`**: JD-Next rubric documentation and item-writing standards
- **`.env`**: Environment variables for all secrets (excluded from git)

---

## Complete Generation Flow

### **Without Upload (Default Behavior)**

```bash
python generate_items_v2.py --topic TP.2 --count 5
```

**Flow:**

1. **Retrieve comprehensive context**

   - ALL mandatory rubric rules (CONSTRUCT, ANATOMY, ITEM_WRITING, etc.)
   - Semantic examples (k=5) from rubric index
   - Similar items (k=8) from exam items index

2. **FOR EACH item (i=1 to 5):**

   - Generate unique `generation_batch_id` (once per session)
   - **RETRY LOOP (max 3 attempts):**
     - Call GPT-4o with comprehensive context + previous 3 scenarios
     - **Post-process #1:** Fix evidence statements (expand "2.e" → "2.e: Understand the concept of...")
     - **Post-process #2:** Shuffle answer options (truly random A/B/C/D)
     - **Check semantic diversity:** Embed scenario → calculate cosine similarity vs previous items
     - **IF similarity > 0.75 AND attempt < 3:** `[REJECT]` → retry
     - **IF similarity > 0.75 AND attempt = 3:** `[WARNING]` → accept anyway
     - **Add metadata:** `generation_batch_id`, `generation_attempt` (1-3), `similarity_at_generation`
   - **Quality scoring:** 8 dimensions (0-5 scale) → determine tier (gold/silver/bronze/needs_revision)
   - Append to items list

3. **Report summary:**

   - Quality distribution (tier counts)
   - Answer distribution (A/B/C/D balance - should be ~25% each)
   - Generation metadata (attempts, similarities)

4. **Output results:**
   - Write to file (`--output items.jsonl`)
   - OR print to stdout

---

### **With Upload Flag**

```bash
python generate_items_v2.py --topic TP.2 --count 5 --upload --upload-quality-threshold bronze
```

**Additional Steps (after generation):**

5. **Filter by quality threshold:**

   - `--upload-quality-threshold gold`: Keep items with score ≥ 4.5
   - `--upload-quality-threshold silver`: Keep items with score ≥ 3.5
   - `--upload-quality-threshold bronze` (default): Keep items with score ≥ 2.5
   - `--upload-quality-threshold all`: Keep everything

6. **FOR EACH item to upload:**

   - Generate unique item ID (UUID)
   - Create searchable content text
   - Generate embedding vector (1536 dims via `text-embedding-3-small`)
   - **Build document with ALL fields:**
     - **Core:** id, topic, domain, evidence, stimulus, stem, options, correct_answer, rationale
     - **Quality:** quality_score, quality_tier, quality_summary, quality_scores_json, improvement_suggestions
     - **Review:** `review_status="pending_review"`, reviewed_at=None, reviewed_by=None, review_decision=None, review_explanation=None
     - **Edit:** was_edited=False, original_version_json=None, edit_summary=None
     - **Generation:** generation_batch_id, generation_attempt, similarity_at_generation, generation_metadata_json
   - Upload to Azure Search index via `upload_items_batch()`

7. **Report upload results:**
   - Total uploaded
   - Succeeded/Failed counts
   - By tier distribution
   - **Review status = "pending_review"** (awaiting human review)

---

## Human Review Workflow (Future Agent Framework)

**When building the review application:**

### **1. Query Pending Items**

```python
from retrieval import get_pending_review_items

items = get_pending_review_items(limit=50)
# Returns items with review_status="pending_review"
```

### **2. Human Reviewer Makes Decision**

**Option A: Upvote (approve as-is)**

```python
from retrieval import update_review_status

update_review_status(
    item_id="abc-123",
    review_decision="upvote",
    reviewed_by="reviewer@example.com"
)
# Sets review_status="approved"
```

**Option B: Upvote + Edit**

```python
update_review_status(
    item_id="abc-123",
    review_decision="upvote",
    reviewed_by="reviewer@example.com",
    edited_fields={
        "stem": "Updated question stem...",
        "option_b": "Corrected distractor..."
    }
)
# Captures original_version_json
# Sets was_edited=True
# Sets review_status="approved_with_edits"
```

**Option C: Downvote (reject)**

```python
update_review_status(
    item_id="abc-123",
    review_decision="downvote",
    review_explanation="Scenario is unrealistic; options are not mutually exclusive",
    reviewed_by="reviewer@example.com"
)
# Sets review_status="rejected"
```

### **3. Analytics & Learning**

```python
from retrieval import get_rejection_patterns, get_review_analytics

# Identify common failure patterns
patterns = get_rejection_patterns(topic="TP.2")
# Shows: review_explanation, similarity_at_generation, quality_tier

# Monitor review progress
analytics = get_review_analytics()
# Returns:
# - status_counts: {'pending_review': 120, 'approved': 45, 'rejected': 12, ...}
# - approval_rate: 78.9%
# - edit_rate: 23.4%
# - avg_quality_by_status: {'approved': 4.2, 'rejected': 3.1}
```

### **4. Use Approved Items for Future Generation**

```python
from retrieval import get_approved_items, retrieve_items_by_quality

# Get gold standard approved items
approved = get_approved_items(limit=100, include_edits=True)

# Use as examples in generation context
gold_items = retrieve_items_by_quality(
    query_text="consideration in contract law",
    quality_tiers=["gold"],
    k=5
)
```

---

## Quality Scoring System

### **8 Dimensions (0-5 scale each):**

1. **Clarity & Readability** - Clear language, no ambiguity
2. **Cognitive Level** - Appropriate difficulty (application/analysis)
3. **Evidence Alignment** - Directly tests specified evidence statements
4. **Plausibility of Distractors** - Wrong answers are tempting but clearly incorrect
5. **Legal Accuracy** - Factually correct with realistic scenarios
6. **Scenario Quality** - Authentic, professional context
7. **Rationale Quality** - Explains correct answer and why others are wrong
8. **Overall Quality** - Holistic assessment

### **4 Quality Tiers:**

- **Gold** (≥4.5): Publication-ready, no revisions needed
- **Silver** (3.5-4.5): Minor revisions, strong foundation
- **Bronze** (2.5-3.5): Moderate revisions needed
- **Needs Revision** (<2.5): Significant issues, major rework required

---

## Review States

| State                 | Description                         | Triggered By                 |
| --------------------- | ----------------------------------- | ---------------------------- |
| `gold_standard`       | Original curated items from dataset | Manual import                |
| `pending_review`      | Awaiting human review               | Auto-upload after generation |
| `approved`            | Reviewed and approved without edits | Human upvote                 |
| `approved_with_edits` | Reviewed, edited, and approved      | Human upvote + edits         |
| `rejected`            | Reviewed and rejected               | Human downvote               |

---

## Setup

### **1. Clone the Repository**

```bash
git clone https://github.com/dotnetspark/aspenmind-dev.git
cd aspenmind-dev
```

### **2. Install Dependencies**

```bash
pip install -r requirements.txt
```

### **3. Configure Environment Variables**

Create a `.env` file with your Azure credentials:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-api-key
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-admin-key
AZURE_EXAM_INDEX=jdnext_exam_items_index
AZURE_RUBRIC_INDEX=jdnext_rubric_index
```

### **4. Create Search Indices**

Run the ingestion notebooks to create indices and upload data:

```bash
# Create exam items index with review/state management fields
jupyter notebook exam_ingestion_pipeline.ipynb

# Create rubric rules index
jupyter notebook rubric_ingestion_pipeline.ipynb
```

### **5. Generate Items**

```bash
# Generate 5 items for topic TP.2 (scored, not uploaded)
python generate_items_v2.py --topic TP.2 --count 5

# Generate and upload bronze-tier or better items
python generate_items_v2.py --topic TP.2 --count 10 --upload --upload-quality-threshold bronze

# Generate with custom temperature and output file
python generate_items_v2.py --topic TP.3 --count 20 --temperature 0.6 --output output/tp3_items.jsonl
```

---

## CLI Reference

### **`generate_items_v2.py` Arguments**

| Argument                     | Type  | Default      | Description                                                       |
| ---------------------------- | ----- | ------------ | ----------------------------------------------------------------- |
| `--topic`                    | str   | **required** | JD-Next topic code (e.g., TP.2, TP.3)                             |
| `--count`                    | int   | 1            | Number of items to generate                                       |
| `--output`                   | str   | None         | Path to write generated items as JSONL                            |
| `--temperature`              | float | 0.4          | Sampling temperature (0.0-1.0)                                    |
| `--retrieval-k`              | int   | 8            | Number of similar items to retrieve for context                   |
| `--no-score`                 | flag  | False        | Skip quality scoring stage (faster but no quality metadata)       |
| `--upload`                   | flag  | False        | Upload generated items to exam index                              |
| `--upload-min-score`         | float | 0.0          | Only upload items with quality score ≥ this value                 |
| `--upload-quality-threshold` | str   | bronze       | Upload items meeting this tier: `gold`, `silver`, `bronze`, `all` |

**Examples:**

```bash
# Generate 5 items, score them, print to stdout
python generate_items_v2.py --topic TP.2 --count 5

# Generate 10 items, upload silver-tier or better
python generate_items_v2.py --topic TP.3 --count 10 --upload --upload-quality-threshold silver

# Generate 20 items with higher temperature, save to file
python generate_items_v2.py --topic TP.1 --count 20 --temperature 0.7 --output output/tp1_creative.jsonl

# Fast generation without scoring (testing only)
python generate_items_v2.py --topic TP.2 --count 3 --no-score
```

---

## Key Functions Reference

### **Generation (`generate_items_v2.py`)**

- `generate_items_batch(topic_code, count, retrieval_k, temperature, validate)` - Main batch generation with retry logic
- `generate_jdnext_item(topic_code, evidence_statements, comprehensive_context, temperature, validate, previous_scenarios)` - Single item generation
- `shuffle_answer_options(item)` - Post-processing: randomize answer positions
- `validate_and_fix_evidence_statements(item, evidence_map)` - Post-processing: expand evidence codes
- `check_scenario_diversity(item, previous_items, threshold)` - Semantic similarity check

### **Retrieval & Context (`retrieval.py`)**

- `retrieve_comprehensive_context(topic_code, query_text, k_examples, k_items)` - Get ALL rubric rules + examples + similar items
- `retrieve_all_rubric_rules(categories)` - Fetch all mandatory rules from rubric index
- `retrieve_rubric_chunks(query_text, k)` - Semantic search for rubric examples
- `retrieve_similar_items(query_text, k)` - Vector search for similar exam items
- `embed(text)` - Generate 1536-dim embedding vector

### **Upload & Quality (`retrieval.py`)**

- `upload_item_to_index(item, review_status)` - Upload single item with review/state fields
- `upload_items_batch(items, review_status)` - Batch upload with summary
- `retrieve_items_by_quality(query_text, min_score, max_score, quality_tiers, k)` - Query by quality filter
- `retrieve_gold_and_low_quality_items(query_text, k_gold, k_low)` - Contrastive learning examples

### **Review Management (`retrieval.py`)**

- `update_review_status(item_id, review_decision, review_explanation, reviewed_by, edited_fields)` - Human review workflow
- `get_pending_review_items(limit)` - Fetch items awaiting review
- `get_approved_items(limit, include_edits)` - Fetch approved items
- `get_rejection_patterns(topic, limit)` - Analyze failure patterns
- `get_review_analytics()` - Summary stats: approval rate, edit rate, quality by status

### **Scoring (`generate_items_v2.py`)**

- `score_item(item)` - 8-dimensional quality scoring (0-5 scale) with tier classification

---

## Architecture & Design Principles

### **Post-Processing > LLM Instructions**

- **Answer shuffling** is done via post-processing (truly random) rather than LLM instructions (deterministic bias)
- **Evidence validation** is done via code (reliable) rather than LLM instructions (inconsistent)
- **Format enforcement** is deterministic and token-efficient

### **Semantic Diversity with Retry Logic**

- Uses **cosine similarity on embeddings** (1536-dim) to detect overly similar scenarios
- **Threshold: 0.75** - items with similarity > 0.75 are rejected and regenerated
- **Max 3 attempts** - prevents infinite loops, accepts after 3 tries even if similar
- **Tracks metadata** - `generation_attempt`, `similarity_at_generation` for analytics

### **Quality Gate Before Human Review**

- Only items meeting quality threshold (default: bronze/2.5+) are uploaded
- Prevents overwhelming reviewers with low-quality items
- **All uploaded items have `review_status="pending_review"`** - human review is required

### **Agent-Ready Design**

- All functions are **stateless** with clear input/output contracts
- Can be directly exposed as **Microsoft Agent Framework tools**
- Supports future workflow: Generate → Review → Approve → Use as Examples

### **Full Traceability**

- Every item knows:
  - **Which batch** it came from (`generation_batch_id`)
  - **How many tries** it took (`generation_attempt`)
  - **How similar** it was to others (`similarity_at_generation`)
  - **Who reviewed it** (`reviewed_by`, `reviewed_at`)
  - **What was edited** (`original_version_json`, `edit_summary`)

---

## Roadmap & Future Work

### **Phase 1: Core Generation (✅ Complete)**

- ✅ Multi-stage generation with comprehensive rubric context
- ✅ Quality scoring (8 dimensions, 4 tiers)
- ✅ Post-processing pipeline (shuffle, validate, diversity)
- ✅ Retry logic with semantic diversity enforcement
- ✅ Batch metadata tracking

### **Phase 2: State Management (✅ Complete)**

- ✅ Index schema with review/state management fields
- ✅ Upload functions with `pending_review` status
- ✅ Review management APIs (update, query, analytics)
- ✅ Edit tracking with version snapshots

### **Phase 3: Agent Framework Migration (🚧 In Progress)**

- 🚧 Convert generation script to Microsoft Agent Framework workflow
- 🚧 Build review application with UI for human-in-the-loop
- 🚧 Implement upvote/downvote with explanations
- 🚧 Add manual item editing interface
- 🚧 Build analytics dashboard (approval rates, quality trends, rejection patterns)

### **Phase 4: Advanced Features (📋 Planned)**

- 📋 Active learning: use rejection patterns to improve generation
- 📋 Contrastive examples: show gold vs low-quality items during generation
- 📋 Multi-reviewer consensus: require 2+ approvals for gold standard
- 📋 Auto-promotion: approved_with_edits → gold_standard after N uses
- 📋 Topic-specific quality models: fine-tune scoring per domain

---

---

## Security & Best Practices

### **Environment Variables**

- **Never commit your `.env` file or secrets to source control**
- The provided `.gitignore` ensures `.env` and other sensitive files are excluded
- Use Azure Key Vault or managed identities for production deployments

### **Data Privacy**

- All exam items and rubric rules are stored in Azure AI Search (private)
- Embeddings are generated using Azure OpenAI (private endpoint)
- No data is sent to public OpenAI APIs

### **Quality Assurance**

- All generated items require human review (`pending_review` status)
- Quality scoring provides objective metrics but doesn't replace human judgment
- Use `--upload-quality-threshold` to filter items before review
- Track rejection patterns to continuously improve generation

### **Cost Optimization**

- Use `--temperature 0.4` (default) for consistent quality
- Set `--retrieval-k 8` (default) for optimal context vs cost
- Use `--no-score` flag for fast prototyping (skips scoring LLM calls)
- Batch generations: `--count 10` is more efficient than 10 separate runs

---

## Troubleshooting

### **Issue: Low diversity (similar scenarios)**

- Increase `--temperature` (e.g., 0.6-0.8) for more creativity
- Check retry logs - items rejected for similarity will show `[REJECT]` → `[RETRY]`
- Review `similarity_at_generation` in generated items

### **Issue: Low quality scores**

- Review `improvement_suggestions` in quality metadata
- Check if evidence statements are aligned with topic
- Ensure rubric index has comprehensive rules and examples

### **Issue: Upload fails**

- Verify Azure Search credentials in `.env`
- Check index exists: run `exam_ingestion_pipeline.ipynb` to create schema
- Ensure items have quality scores (don't use `--no-score` with `--upload`)

### **Issue: Items always get answer "A"**

- ✅ **FIXED** - Answer shuffling is now post-processing (truly random)
- Check answer distribution in generation summary

### **Issue: Evidence statements show codes only ("2.e")**

- ✅ **FIXED** - Auto-fix expands codes to full text
- Verify `EVIDENCE_MAP` in `generate_items_v2.py` has correct mappings

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License

MIT License

---

## Author

Created by [dotnetspark](https://github.com/dotnetspark)

---

## Acknowledgments

- **Azure OpenAI** for GPT-4o and text-embedding-3-small models
- **Azure AI Search** for vector search and hybrid retrieval
- **JD-Next** for item-writing rubric standards and gold standard exam items
- **Microsoft Agent Framework** (future integration target)

---

## Contact & Support

For questions, issues, or feature requests:

- Open an issue on GitHub: [aspenmind-dev/issues](https://github.com/dotnetspark/aspenmind-dev/issues)
- Email: [dotnetspark@example.com](mailto:dotnetspark@example.com)

---

**Last Updated:** January 3, 2026  
**Version:** 2.0 (State Management + Human-in-the-Loop Review)
