# DocIntel local development without Docker

The Docker Compose stack is optional for development. On an 8 GB laptop, avoid building PyTorch images locally.

1. Use an existing PostgreSQL 16 database with the `vector` extension enabled (a free hosted pgvector-compatible PostgreSQL database is fine). Keep its credentials private.
2. Create `backend/.env` or set environment variables in your terminal: `DATABASE_URL`, `GROQ_API_KEY`, `JWT_SECRET`, `ENABLE_RERANKER=false`. **Note:** `backend/.env` is not loaded automatically by the current backend; export variables or use `python-dotenv` to load them.
3. From `backend/`: `pip install -r requirements.txt`, then `python -m uvicorn main:app --reload`.
4. From `frontend/`: `npm install`, then `npm start`.
5. Visit `http://localhost:3000`. Register, upload a PDF, and wait for status ready.
6. Upload two policy versions using the same policy key, then compare them. Page references refer to the PDF pages extracted during ingestion.
7. Run comparison unit tests from `backend/`: `python -m unittest discover -s tests -p "test_version_compare.py"`.

**Limitations:** This version comparison is a deterministic sentence-level text diff, not a semantic conflict detector. Text may be duplicated across overlapping chunks, and complex PDFs can generate noisy diffs. There is no OCR or durable job queue. Version activation still follows ingestion completion order, not effective date. Citations are retrieved excerpts, not independently validated answer claims. Keep uploads private; do not commit confidential PDFs.

**Free infrastructure:** Prefer a free pgvector-capable hosted PostgreSQL service for development, subject to its current quota and extension support. Groq's free tier can be used with rate limits. Local MiniLM embeddings still use laptop RAM; disabling the cross-encoder helps.
