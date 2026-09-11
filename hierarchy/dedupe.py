"""
Exact-duplicate detection, run BEFORE any LLM hierarchy call.

Two items whose names are identical once case/whitespace-normalized are
the same real-world dish written differently (e.g. the real
"Aloo baingan masala" vs "Aloo Baingan Masala" pair found in the live
catalog) — that's a data-quality / merge problem, not a parent_of
hierarchy relationship, and it doesn't need an LLM to detect. Catching it
here, deterministically, also means the LLM's prompt (and any future
per-item cost at real scale) isn't wasted on redundant near-identical rows.

Only ONE representative per duplicate cluster gets sent on to hierarchy
classification; the rest are reported separately as merge candidates for a
human to actually resolve (this script never merges/deletes anything).
"""

import re


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def find_duplicate_clusters(items: list[dict]) -> tuple[list[list[dict]], list[dict]]:
    """
    Returns (duplicate_clusters, items_for_classification).
    duplicate_clusters: groups of 2+ items that normalize to the same name.
    items_for_classification: one representative per normalized name
    (the first one seen) — i.e. every distinct dish, deduplicated.
    """
    by_normalized: dict[str, list[dict]] = {}
    for item in items:
        by_normalized.setdefault(_normalize(item["name"]), []).append(item)

    duplicate_clusters = [group for group in by_normalized.values() if len(group) > 1]
    items_for_classification = [group[0] for group in by_normalized.values()]
    return duplicate_clusters, items_for_classification
