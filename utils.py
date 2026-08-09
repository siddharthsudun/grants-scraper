"""
Deduplication, CSV export, and progress utilities.
"""
import csv
import json
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Dict, Any


CSV_COLUMNS = [
    "name",
    "provider",
    "type",
    "amount",
    "eligibility",
    "deadline",
    "apply_url",
    "apply_email",
    "apply_method",
    "insider_tips",
    "prerequisites",
    "relevance_score",
    "relevance_reason",
    "tags",
    "source_url",
    "source_platform",
]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deduplicate_grants(grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate grants by name similarity (>0.85 = same grant).
    Keeps the one with higher relevance_score.
    """
    deduped = []
    for g in grants:
        name = g.get("name", "")
        if not name:
            continue
        matched = False
        for i, existing in enumerate(deduped):
            if _similarity(name, existing.get("name", "")) > 0.85:
                # Keep higher relevance
                if g.get("relevance_score", 0) > existing.get("relevance_score", 0):
                    deduped[i] = g
                matched = True
                break
        if not matched:
            deduped.append(g)
    return deduped


def save_to_csv(grants: List[Dict[str, Any]], path: Path) -> None:
    # Sort by relevance descending
    grants_sorted = sorted(grants, key=lambda x: x.get("relevance_score", 0), reverse=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for g in grants_sorted:
            row = {}
            for col in CSV_COLUMNS:
                val = g.get(col, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                elif isinstance(val, dict):
                    val = json.dumps(val)
                row[col] = val
            writer.writerow(row)

    print(f"\n    CSV written: {path}")
    print(f"    Columns: {', '.join(CSV_COLUMNS)}")


def load_raw(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())
