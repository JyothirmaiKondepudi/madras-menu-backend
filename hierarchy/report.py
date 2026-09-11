"""Renders a plain markdown report from validated/rejected proposals — this
report IS today's review step (see plan doc). Nothing gets written to the
database from this script."""

from .validate import ValidationResult


def render_report(
    items: list[dict],
    result: ValidationResult,
    duplicate_clusters: list[list[dict]] | None = None,
) -> str:
    name_by_id = {item["id"]: item["name"] for item in items}
    duplicate_clusters = duplicate_clusters or []

    lines = ["# Proposed dish hierarchy — review before applying\n"]

    if duplicate_clusters:
        lines.append(
            f"- {len(duplicate_clusters)} exact-duplicate clusters found "
            "(case/whitespace-only differences) — merge candidates, "
            "NOT sent for hierarchy classification, see below"
        )
    lines.append(f"- {len(result.valid)} valid proposals")
    lines.append(f"- {len(result.rejected)} rejected proposals (see below — not applied)")
    lines.append(f"- {len(result.missing_item_ids)} items got no proposal at all\n")

    if duplicate_clusters:
        lines.append("## Exact duplicates — merge candidates, not a hierarchy relationship\n")
        lines.append(
            "These rows are the same real-world dish, differing only by case/whitespace. "
            "Only the first of each group was sent on for hierarchy classification below; "
            "the rest need a human decision to merge/delete, not a parent_of edge.\n"
        )
        for cluster in duplicate_clusters:
            names = ", ".join(f'"{item["name"]}"' for item in cluster)
            lines.append(f"- {names}")
        lines.append("")

    roots = [p for p in result.valid if p["parent_id"] is None]
    children = [p for p in result.valid if p["parent_id"] is not None]

    lines.append(f"## Valid: {len(roots)} roots, {len(children)} parent_of edges\n")
    lines.append("| Child | Parent | Confidence | Reason |")
    lines.append("|---|---|---|---|")
    for p in sorted(children, key=lambda p: name_by_id.get(p["item_id"], p["item_id"])):
        child_name = name_by_id.get(p["item_id"], p["item_id"])
        parent_name = name_by_id.get(p["parent_id"], p["parent_id"])
        lines.append(f"| {child_name} | {parent_name} | {p['confidence']} | {p['reason']} |")

    lines.append("\n### Roots (no parent)\n")
    for p in sorted(roots, key=lambda p: name_by_id.get(p["item_id"], p["item_id"])):
        lines.append(f"- {name_by_id.get(p['item_id'], p['item_id'])} — {p['reason']}")

    if result.rejected:
        lines.append("\n## Rejected — did NOT pass validation, needs a human look\n")
        lines.append("| Item | Proposed parent | Why rejected |")
        lines.append("|---|---|---|")
        for r in result.rejected:
            item_name = name_by_id.get(r.item_id, r.item_id)
            parent_name = name_by_id.get(r.parent_id, r.parent_id) if r.parent_id else "—"
            lines.append(f"| {item_name} | {parent_name} | {r.reason} |")

    if result.missing_item_ids:
        lines.append("\n## Items with no proposal at all\n")
        for item_id in result.missing_item_ids:
            lines.append(f"- {name_by_id.get(item_id, item_id)}")

    return "\n".join(lines) + "\n"
