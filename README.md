# AspenMind Exam Item Generation Pipeline

This project provides a pipeline for generating, retrieving, and managing scenario-based multiple-choice exam items for professional exams in law, using Azure OpenAI and Azure AI Search.

## Purpose

- Automate the creation of high-quality, legally accurate exam items aligned to specific evidence statements.
- Support large-scale item generation for educational, assessment, or training purposes.
- Enable retrieval-augmented generation (RAG) using vector search over prototype items and evidence statements.

## Features

- **Vector Search**: Uses Azure AI Search to retrieve relevant exam prototypes and evidence.
- **LLM Generation**: Uses Azure OpenAI (GPT-4o) to generate new exam items, with prompt engineering for legal accuracy and diversity.
- **Evidence Alignment**: Ensures each item is explicitly linked to one or more evidence statements.
- **Output Handling**: Saves generated items as clean JSON files, ready for review or ingestion.
- **Security**: All secrets and keys are managed via a `.env` file (never committed to source control).

## Structure

- `retrieval_and_generation.py`: Main script for embedding, retrieval, and item generation.
- `maintenance.ipynb`: Utilities for index management and evidence inspection.
- `dataset/`: Source CSVs and data files.
- `output/`: Generated exam items in JSON format.
- `.env`: Environment variables for all secrets (excluded from git).

## Setup

1. Clone the repo.
2. Create a `.env` file with your Azure and OpenAI credentials (see `.env.example`).
3. Run the main script:
   ```
   python retrieval_and_generation.py --evidence-prefix 01.02 --topic "consideration in contract law" --num-items 20
   ```

## Security

- **Never commit your `.env` file or secrets to source control.**
- The provided `.gitignore` ensures `.env` and other sensitive files are excluded.

## License

MIT License

## Author

Created by [dotnetspark](https://github.com/dotnetspark)
