#!/usr/bin/env python3
"""Proposes parent_of edges for the dish hierarchy and writes a markdown report
for human review. Never writes to the database itself.

Usage:
    # Dry run — hardcoded fixture, fake LLM response, no DB or setup needed
    python3 propose_hierarchy.py --dry-run

    # Real run — reads items from Postgres. call_llm() isn't wired up yet.
    DATABASE_URL="postgresql://jyothirmaikondepudi@localhost:5432/madras_menu_local" \\
        python3 propose_hierarchy.py
"""

import argparse
import json
import os
import sys

# Make `hierarchy` importable regardless of the caller's cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hierarchy.dedupe import find_duplicate_clusters
from hierarchy.prompt import build_prompt
from hierarchy.report import render_report
from hierarchy.schema import RESPONSE_JSON_SCHEMA
from hierarchy.validate import validate_proposals


def fetch_items_from_db(database_url: str) -> list[dict]:
    import psycopg2  # local import: only required for a real (non-dry-run) run

    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, course, cuisine_tags FROM menu_items ORDER BY name")
        rows = cur.fetchall()
    return [
        {"id": row[0], "name": row[1], "course": row[2], "cuisine_tags": row[3]}
        for row in rows
    ]


def call_llm(items: list[dict]) -> dict:
    """TODO: build_prompt(items) + RESPONSE_JSON_SCHEMA, call the LLM, return
    a parsed {"proposals": [...]} dict matching _dry_run_response()'s shape."""
    _ = build_prompt(items)
    raise NotImplementedError(
        "call_llm() isn't wired up yet — run with --dry-run for now, "
        "or fill this in once the Vertex AI SDK is set up."
    )


def _dry_run_fixture() -> list[dict]:
    """Small hardcoded item set, including a near-duplicate pair, enough to
    exercise every code path without a DB or LLM."""
    return [
        {"id": "a1", "name": "Basmati Rice", "course": "side", "cuisine_tags": ["north_indian"]},
        {"id": "a2", "name": "Chicken Biryani", "course": "main", "cuisine_tags": ["hyderabadi", "south_indian"]},
        {"id": "a3", "name": "Hyderabadi Chicken Biryani", "course": "main", "cuisine_tags": ["hyderabadi"]},
        {"id": "a4", "name": "Vegetable Biryani", "course": "main", "cuisine_tags": ["south_indian"]},
        {"id": "a5", "name": "Aloo Baingan Masala", "course": "main", "cuisine_tags": ["north_indian"]},
        {"id": "a6", "name": "Aloo baingan masala", "course": "main", "cuisine_tags": ["north_indian"]},
    ]


def _dry_run_response() -> dict:
    """A fake LLM response — includes one bad case (a1/a2 proposed as each
    other's parent, a cycle) to prove validate_proposals() catches it."""
    return {
        "proposals": [
            {
                "item_id": "a1",
                "parent_id": "a2",
                "reason": "(intentionally wrong, to test validation) mislabeled as a biryani variant",
                "confidence": "low",
            },
            {
                "item_id": "a2",
                "parent_id": "a1",
                "reason": "biryani is a rice preparation",
                "confidence": "high",
            },
            {
                "item_id": "a3",
                "parent_id": "a2",
                "reason": "regional variant of chicken biryani",
                "confidence": "high",
            },
            {
                "item_id": "a4",
                "parent_id": "a1",
                "reason": "biryani is a rice preparation",
                "confidence": "medium",
            },
            {
                "item_id": "a5",
                "parent_id": None,
                "reason": "generic curry, not a variant of anything else in this list",
                "confidence": "medium",
            },
            # "a6" has no entry — find_duplicate_clusters() filters it out first
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use a hardcoded fixture instead of the DB, and a fake LLM response instead of a real call.",
    )
    parser.add_argument(
        "--out",
        default="hierarchy_report.md",
        help="Where to write the markdown report (default: hierarchy_report.md)",
    )
    args = parser.parse_args()

    if args.dry_run:
        all_items = _dry_run_fixture()
    else:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            print("DATABASE_URL is not set. Either set it or use --dry-run.", file=sys.stderr)
            return 1
        all_items = fetch_items_from_db(database_url)
        print(f"Fetched {len(all_items)} items from the database.")

    duplicate_clusters, items = find_duplicate_clusters(all_items)
    if duplicate_clusters:
        print(f"Found {len(duplicate_clusters)} exact-duplicate cluster(s) — excluded from classification.")

    if args.dry_run:
        response = _dry_run_response()
    else:
        response = call_llm(items)  # will raise NotImplementedError today

    result = validate_proposals(items, response["proposals"])
    report = render_report(items, result, duplicate_clusters)

    with open(args.out, "w") as f:
        f.write(report)

    print(f"Wrote report to {args.out}")
    print(f"  valid: {len(result.valid)}  rejected: {len(result.rejected)}  missing: {len(result.missing_item_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
