from evaluation.benchmark import scores, hit
from langchain_core.documents import Document

def test_scores():
    assert scores([1, 3, None]) == {"hit_at_1": 0.3333, "hit_at_3": 0.6667, "hit_at_5": 0.6667, "mrr": 0.4444}

def test_evidence_match():
    doc = Document(page_content="The total cost is 50 dollars.", metadata={"source": "docs/example.pdf", "page": 1})
    example = {"document": "example.pdf", "evidence": [{"page": 2, "quote": "total cost is 50 dollars"}]}
    assert hit(doc, example)
    assert not hit(doc, {**example, "document": "other.pdf"})
