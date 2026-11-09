"""Offline retrieval evaluation for the existing PDF RAG baseline.

Run from backend/: python -m evaluation.benchmark --dataset evaluation/questions.jsonl
"""
import argparse
import json
import re
from pathlib import Path

def normalize(value):
    return re.sub(r"\s+", " ", value).strip().casefold()

def hit(doc, item):
    if Path(str(doc.metadata.get("source", ""))).name.casefold() != Path(item["document"]).name.casefold():
        return False
    page = int(doc.metadata.get("page", -1)) + 1
    return any(page == e["page"] and normalize(e["quote"]) in normalize(doc.page_content)
               for e in item["evidence"])

def scores(ranks, ks=(1, 3, 5)):
    if not ranks:
        raise ValueError("Benchmark is empty")
    result = {f"hit_at_{k}": round(sum(r is not None and r <= k for r in ranks) / len(ranks), 4) for k in ks}
    result["mrr"] = round(sum(1 / r for r in ranks if r is not None) / len(ranks), 4)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/questions.jsonl"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("evaluation/pdfs"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/baseline.json"))
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    if args.chunk_size <= 0 or args.chunk_overlap < 0 or args.chunk_overlap >= args.chunk_size or args.k < 1:
        parser.error("Invalid chunking or retrieval parameters")
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    items = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not items:
        raise ValueError("No evaluation questions found")
    docs = []
    for name in sorted({item["document"] for item in items}):
        path = args.pdf_dir / Path(name).name
        if not path.is_file():
            raise FileNotFoundError(path)
        docs.extend(PyPDFLoader(str(path)).load())
    splitter = RecursiveCharacterTextSplitter(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap,
                                                separators=["\n\n", "\n", ". ", " ", ""])
    chunks = splitter.split_documents(docs)
    index = FAISS.from_documents(chunks, HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))
    records = []
    for item in items:
        retrieved = index.similarity_search(item["question"], k=args.k)
        rank = next((i for i, doc in enumerate(retrieved, 1) if hit(doc, item)), None)
        records.append({"id": item["id"], "question": item["question"], "first_evidence_rank": rank,
                        "retrieved": [{"source": Path(str(doc.metadata.get("source", ""))).name,
                                       "page": int(doc.metadata.get("page", -1)) + 1,
                                       "evidence_match": hit(doc, item)} for doc in retrieved]})
    report = {"configuration": {"embedding": "all-MiniLM-L6-v2", "chunk_size_characters": args.chunk_size,
                                "chunk_overlap_characters": args.chunk_overlap, "retrieval": "FAISS similarity"},
              "summary": {"questions": len(items), "chunks": len(chunks),
                          **scores([record["first_evidence_rank"] for record in records], (1, 3, args.k))},
              "examples": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Saved {args.output}")

if __name__ == "__main__":
    main()
