"""Deterministic document version comparison. No LLM or model downloads required."""
import difflib
import re

def normalize_lines(chunks):
    pages = {}
    for chunk in chunks:
        page = int(chunk["page"])
        pages.setdefault(page, []).append(chunk["content"])
    lines = []
    for page, texts in sorted(pages.items()):
        # Chunk overlap can duplicate text; compare per-page lines with deduplication.
        seen = set()
        for text in texts:
            for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
                line = " ".join(raw.split()).strip()
                if len(line) < 12 or line.casefold() in seen:
                    continue
                seen.add(line.casefold())
                lines.append({"page": page, "text": line})
    return lines

def compare_versions(old, new, max_changes=100):
    left = normalize_lines(old["chunks"])
    right = normalize_lines(new["chunks"])
    matcher = difflib.SequenceMatcher(
        a=[item["text"].casefold() for item in left],
        b=[item["text"].casefold() for item in right],
        autojunk=False)
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes.append({
            "type": {"replace": "modified", "delete": "removed", "insert": "added"}[tag],
            "before": left[i1:i2][:10],
            "after": right[j1:j2][:10],
        })
        if len(changes) >= max_changes:
            break
    return {"old": old["document"], "new": new["document"],
            "changes": changes, "change_count": len(changes),
            "truncated": len(changes) >= max_changes,
            "method": "Deterministic sentence-level text diff; not semantic conflict detection"}
