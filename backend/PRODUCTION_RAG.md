# Production-style RAG upgrade (experimental)

## Start (Docker, free local database)

Create a root `.env` containing `GROQ_API_KEY=...` and a long random `JWT_SECRET=...`.
Run `docker compose up --build`. Backend: http://localhost:8000/docs.

1. POST `/auth/register` with email/password; POST `/auth/login` for a bearer token.
2. Authorize Swagger with the bearer token. POST `/upload` (max 10 MB PDF).
3. Poll GET `/documents` until status is `ready`; then POST `/ask`.
4. Answers include page-numbered source passages.

## Architecture

PDF -> FastAPI upload -> background ingestion -> MiniLM embeddings -> PostgreSQL pgvector + tsvector
Question -> owner-scoped vector/keyword search -> RRF -> optional local cross-encoder -> Groq Llama -> citations.

## Honest limitations

- BackgroundTasks is **in-process**, not a durable Celery/Redis queue. A crash can leave uploads pending.
- PostgreSQL hybrid retrieval currently uses exact vector sorting and full-text search. Add an ANN index for scale.
- Prompt-based grounding and citations reduce hallucinations but **do not guarantee faithfulness**; passages are not independently validated.
- Scanned PDFs require OCR, not implemented.
- No Redis caching or token streaming yet.
- Current React UI needs login/token handling; use Swagger API in the meantime.
- Docker runs locally; this is **not deployed**. Groq free tier has rate limits.
- Baseline benchmark from Step 1 must be rerun with this retriever before claiming any accuracy improvements.
- Do not deploy publicly without further hardening (rate limiting, email validation, secret management, migrations, upload scanning and durable jobs).
