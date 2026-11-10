"""Compare FAISS, hybrid BM25+dense RRF, and optional cross-encoder reranking.

From backend/: python -m evaluation.compare_retrievers
Requires the same private evaluation/pdfs and questions.jsonl as baseline.
"""
import argparse
import json
import re
from pathlib import Path

from evaluation.benchmark import hit, page_hit, scores


def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.casefold())


def rrf(dense, lexical, k=60):
    """Fuse ranked chunk indices; ties are deterministic."""
    result = {}
    for ranked in (dense, lexical):
        for rank, idx in enumerate(ranked, 1):
            result[idx] = result.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(result, key=lambda idx: (-result[idx], idx))


def evaluate(items, documents, ranks, top_k):
    records = []
    for item, indices in zip(items, ranks):
        retrieved = [documents[i] for i in indices[:top_k]]
        records.append({
            "id": item["id"],
            "first_page_rank": next((n for n, doc in enumerate(retrieved, 1) if page_hit(doc, item)), None),
            "first_evidence_rank": next((n for n, doc in enumerate(retrieved, 1) if hit(doc, item)), None),
            "retrieved": [{"source": Path(str(doc.metadata.get("source", ""))).name,
                           "page": int(doc.metadata.get("page", -1)) + 1,
                           "page_match": page_hit(doc, item),
                           "evidence_match": hit(doc, item)} for doc in retrieved]
        })
    return {
        "page_retrieval": scores([r["first_page_rank"] for r in records], (1, 3, top_k)),
        "exact_evidence": scores([r["first_evidence_rank"] for r in records], (1, 3, top_k)),
        "examples": records,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/questions.jsonl"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("evaluation/pdfs"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/comparison.json"))
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--rerank", action="store_true", help="Download and use local cross-encoder; no API key needed")
    args = parser.parse_args()
    if args.chunk_size <= 0 or not 0 <= args.chunk_overlap < args.chunk_size or args.k < 1 or args.candidates < args.k:
        parser.error("Invalid chunking or retrieval parameters")
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    from rank_bm25 import BM25Okapi

    items = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not items:
        raise ValueError("No evaluation questions")
    pages = []
    for name in sorted({item["document"] for item in items}):
        path = args.pdf_dir / Path(name).name
        if not path.is_file():
            raise FileNotFoundError(path)
        pages.extend(PyPDFLoader(str(path)).load())
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap,
        separators=["\\n\\n", "\\n", ". ", " ", ""]
    ).split_documents(pages)
    # Use stable integer IDs to map FAISS results to the same chunks as BM25.
    for i, chunk in enumerate(chunks):
        chunk.metadata["_eval_idx"] = i
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    index = FAISS.from_documents(chunks, embeddings)
    bm25 = BM25Okapi([tokenize(doc.page_content) or [""] for doc in chunks])
    dense_runs, hybrid_runs = [], []
    for item in items:
        question = item["question"]
        dense_docs = index.similarity_search(question, k=min(len(chunks), args.candidates))
        dense = [doc.metadata["_eval_idx"] for doc in dense_docs]
        lexical_scores = bm25.get_scores(tokenize(question))
        lexical = sorted(range(len(chunks)), key=lambda i: (-lexical_scores[i], i))[:args.candidates]
        dense_runs.append(dense)
        hybrid_runs.append(rrf(dense, lexical))
    results = {
        "configuration": {
            "embedding": "all-MiniLM-L6-v2", "lexical": "BM25Okapi",
            "fusion": "reciprocal rank fusion (k=60)",
            "chunk_size_characters": args.chunk_size, "chunk_overlap_characters": args.chunk_overlap,
            "top_k": args.k, "candidate_pool_per_retriever": args.candidates,
            "note": "Offline BM25+FAISS proxy; not a benchmark of PostgreSQL/pgvector deployment."
        },
        "questions": len(items), "chunks": len(chunks),
        "faiss": evaluate(items, chunks, dense_runs, args.k),
        "hybrid": evaluate(items, chunks, hybrid_runs, args.k),
    }
    if args.rerank:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        reranked = []
        for item, indices in zip(items, hybrid_runs):
            pool = indices[:args.candidates]
            values = model.predict([(item["question"], chunks[i].page_content) for i in pool])
            reranked.append(sorted(pool, key=lambda i: (-float(values[pool.index(i)]), pool.index(i))))
        results["hybrid_reranked"] = evaluate(items, chunks, reranked, args.k)
        results["configuration"]["reranker"] = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({mode: {"page_retrieval": results[mode]["page_retrieval"],
                             "exact_evidence": results[mode]["exact_evidence"]}
                      for mode in ("faiss", "hybrid", "hybrid_reranked") if mode in results}, indent=2))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
