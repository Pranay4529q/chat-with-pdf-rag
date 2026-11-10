# DocIntel: evidence-based document intelligence

## Product problem
Teams rely on large, changing policy, SOP, contract, and technical-document collections.
A chat answer is unsafe when it quotes the wrong version, omits conflicting clauses, or
cannot show the evidence. The target product is an authenticated workspace for
traceable document answers and comparisons, not a generic PDF chatbot.

## Status
**Existing baseline:** PDF ingestion, FastAPI/React Q&A, MiniLM/FAISS, Groq,
offline evaluation. The original 35-question thesis baseline had page Hit@5
22/35 and strict evidence Hit@5 3/35. These measure retrieval, not answer correctness.

**Implemented in this PR:** reproducible offline comparison of identical chunks,
questions and embeddings under FAISS, BM25+FAISS reciprocal rank fusion, and
optional local cross-encoder reranking. Results are written to
`evaluation/results/comparison.json`. No Azure/OpenAI API is required.
This is a local evaluation proxy, **not** proof of performance of the pgvector
hybrid implementation.

**Proposed in other PRs / requires integration testing:** pgvector storage,
JWT document isolation, hybrid search, citations, Docker Compose.

**Not implemented:** DOCX/PPTX, SSE, document versioning, cross-document
conflict detection, durable background jobs, load testing, Azure Blob.

## Reproduce
From `backend/`, with your private thesis PDF and questions JSONL already in
`evaluation/pdfs/` and `evaluation/questions.jsonl`:

```powershell
pip install -r requirements.txt
python -m evaluation.compare_retrievers
python -m evaluation.compare_retrievers --rerank
```

The second command runs a local cross-encoder (model download required).
Compare both page-level and strict quote-level metrics. Avoid making claims of
improvement until you have the resulting scores. Do not commit private PDFs
or confidential evaluation examples.

## Product roadmap (in priority order)
1. Verify retrieval improvements; inspect failed queries and gold evidence.
2. Harden authentication, ingestion jobs, ownership isolation, and citations.
3. Add DOCX/PPTX extraction with reliable page/slide provenance.
4. Implement policy/document versioning, superseded-document exclusion,
   effective dates, and a compare-versions view.
5. Add conflict/ambiguity detection and abstention with cited evidence.
6. Add SSE streaming, latency measurements, load tests and integration tests.

**Resume positioning once tested:** Built an evidence-based document intelligence
workspace for policy and technical-document search with authenticated access,
hybrid retrieval, reranking, version-aware citations and reproducible evaluation.
Only list version-aware capabilities after implementing and validating them.
