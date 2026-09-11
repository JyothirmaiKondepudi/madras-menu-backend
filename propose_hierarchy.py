#!/usr/bin/env python3
"""
Prototype: propose parent_of edges for the dish hierarchy, from real (or
fixture) MenuItem rows. See the plan doc:
~/.claude/plans/declarative-baking-cookie.md

This script never writes to the database — it only produces a markdown
report for a human to review (today's review step, mirroring this repo's
existing draft -> /review -> promote pattern for menu items themselves).

Usage:
    # Dry run — no DB, no LLM, uses a small hardcoded fixture (including a
    # deliberately bad proposal) to prove the validation/report plumbing
    # works end-to-end. Safe to run right now, no setup required beyond
    # the packages already in this repo (or in a venv you install into).
    python3 propose_hierarchy.py --dry-run

    # Real run — reads seeded items from a local Postgres DB and calls the
    # LLM. NOT WIRED UP YET: call_llm() below raises NotImplementedError
    # until a real provider (Vertex AI, or the Anthropic API) is added —
    # see DESIGN.md for why the first real batch was classified inline by
    # Claude in a coding session instead, at zero API cost.
    DATABASE_URL="postgresql://jyothirmaikondepudi@localhost:5432/madras_menu_local" \\
        python3 propose_hierarchy.py
"""

import argparse
import json
import os
import sys

# Make `hierarchy` importable regardless of the caller's cwd (so
# `python3 scripts/propose_hierarchy.py` works from the repo root, not
# just from inside scripts/).
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
    """
    TODO: wire up the Vertex AI SDK here once GCP billing/project is set
    up. Build the prompt with build_prompt(items), pass RESPONSE_JSON_SCHEMA
    as the model's response_schema (structured JSON output), and return the
    parsed {"proposals": [...]} dict — same shape _dry_run_response()
    returns below, so nothing else in this script needs to change.
    """
    _ = build_prompt(items)  # already usable today; just not sent anywhere yet
    raise NotImplementedError(
        "call_llm() isn't wired up yet — run with --dry-run for now, "
        "or fill this in once the Vertex AI SDK is set up."
    )


def _dry_run_fixture() -> list[dict]:
    """Small hardcoded item set, styled after real dish names in the
    catalog (including a real-looking near-duplicate, like the actual
    'Aloo baingan masala' / 'Aloo Baingan Masala' duplicate found in the
    live data) — enough to exercise every code path without a DB or LLM."""
    return [
        {"id": "a1", "name": "Basmati Rice", "course": "side", "cuisine_tags": ["north_indian"]},
        {"id": "a2", "name": "Chicken Biryani", "course": "main", "cuisine_tags": ["hyderabadi", "south_indian"]},
        {"id": "a3", "name": "Hyderabadi Chicken Biryani", "course": "main", "cuisine_tags": ["hyderabadi"]},
        {"id": "a4", "name": "Vegetable Biryani", "course": "main", "cuisine_tags": ["south_indian"]},
        {"id": "a5", "name": "Aloo Baingan Masala", "course": "main", "cuisine_tags": ["north_indian"]},
        {"id": "a6", "name": "Aloo baingan masala", "course": "main", "cuisine_tags": ["north_indian"]},
    ]


def _dry_run_response() -> dict:
    """A fake LLM response — deliberately includes one bad case (a1/a2
    proposed as each other's parent, a genuine cycle) to prove
    validate_proposals() actually catches it rather than silently trusting
    every proposal."""
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
            # Note: "a6" (the "Aloo baingan masala" casing duplicate of a5)
            # deliberately has no entry here — it gets filtered out by
            # find_duplicate_clusters() before classification even happens,
            # so the LLM (real or fake) never sees it as a separate item.
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
