"""Finds items whose names are the same once case/whitespace-normalized 
(e.g. "Aloo baingan masala" vs "Aloo Baingan Masala") before they 
reach LLM hierarchy classification."""

import re


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def find_duplicate_clusters(items: list[dict]) -> tuple[list[list[dict]], list[dict]]:
    """Returns (duplicate_clusters, items_for_classification): groups of 2+ items
    sharing a normalized name, and one representative per group."""
    by_normalized: dict[str, list[dict]] = {}
    for item in items:
        by_normalized.setdefault(_normalize(item["name"]), []).append(item)

    duplicate_clusters = [group for group in by_normalized.values() if len(group) > 1]
    items_for_classification = [group[0] for group in by_normalized.values()]
    return duplicate_clusters, items_for_classification
