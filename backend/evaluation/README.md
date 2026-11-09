# Step 1: Baseline retrieval evaluation

This standalone script benchmarks the existing FAISS + MiniLM retriever without changing the API or UI. No paid model or API key is required.

## Prepare

From `backend/`, install `requirements.txt` and optionally `pytest`. Place PDFs under `evaluation/pdfs/`. Copy `evaluation/questions.example.jsonl` to `evaluation/questions.jsonl` and replace the placeholder with 30–50 **human-verified** questions from those PDFs. Each record requires an ID, question, PDF filename, expected answer, and one or more exact evidence quotes with **1-based** page numbers. Evidence quotes must fit inside one chunk. Never treat the example as a scored benchmark.

## Run

```powershell
python -m evaluation.benchmark
python -m evaluation.benchmark --chunk-size 500 --chunk-overlap 100 --output evaluation/results/chunk500.json
python -m pytest tests/test_evaluation_metrics.py
```

Reports include Hit@1, Hit@3, Hit@5 and mean reciprocal rank (MRR), plus per-question evidence matches. Hit requires the correct PDF, page and exact normalized quote. The baseline uses **characters**, not tokens, to match the existing application.

## Limits

This evaluates retrieval only, **not answer faithfulness**. Add a separately validated faithfulness evaluation before claiming grounded answer accuracy. Scores are not available until the curated questions are run. Keep benchmark questions, PDFs and results out of git unless they are licensed and safe to publish.
