import json
import re
from pathlib import Path

KB_PATH = Path(__file__).parent / "data" / "clinic_kb.json"


def _load_entries() -> list[dict]:
    with KB_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def retrieve_clinic_info(query: str, top_k: int = 2) -> str:
    """Simple keyword retrieval over the small clinic FAQ."""
    query_tokens = set(re.findall(r"[a-z0-9']+", query.lower()))
    if not query_tokens:
        return ""

    scored: list[tuple[int, dict]] = []
    for entry in _load_entries():
        blob = f"{entry['title']} {entry['text']}".lower()
        tokens = set(re.findall(r"[a-z0-9']+", blob))
        score = len(query_tokens & tokens)
        if score:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return ""

    chunks = [e["text"] for _, e in scored[:top_k]]
    return "\n\n".join(chunks)
