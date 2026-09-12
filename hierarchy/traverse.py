"""
Depth-first traversal of the item_relationships tree, from a given root
down through its parent_of children. Real database code (psycopg2), not a
report-generation script — this is the kind of query the future
knowledge-graph/RAG retrieval layer will need too (walk down from a broad
node to everything more specific beneath it).

Cycle-safe even though the DB itself shouldn't contain one (validate.py's
cycle check should have caught it before any edge was written) — `visited`
is a defensive backstop, not a substitute for that check.
"""

import argparse
import os
from datetime import date

import psycopg2


def get_children(cur, parent_id: str) -> list[tuple[str, str]]:
    """Direct children of parent_id: dishes whose parent_of edge points AT
    it. Returns (id, name) pairs. `to_item_id` is the parent side of the
    edge, `from_item_id` the child side — see DESIGN.md for why."""
    cur.execute(
        """
        SELECT m.id, m.name
        FROM item_relationships r
        JOIN menu_items m ON m.id = r.from_item_id
        WHERE r.to_item_id = %s AND r.relationship_type = 'parent_of'
        ORDER BY m.name
        """,
        (parent_id,),
    )
    return cur.fetchall()


def dfs(cur, root_id: str, root_name: str, depth: int = 0, visited: set | None = None) -> list[str]:
    """Returns the subtree rooted at root_id as indented lines, deepest-first
    traversal order (a child's own children print before its next sibling)."""
    if visited is None:
        visited = set()
    if root_id in visited:
        return [f"{'  ' * depth}- {root_name}  [CYCLE — should never happen, validate.py should have caught this]"]
    visited.add(root_id)

    lines = [f"{'  ' * depth}- {root_name}"]
    for child_id, child_name in get_children(cur, root_id):
        lines.extend(dfs(cur, child_id, child_name, depth + 1, visited))
    return lines


def find_true_roots(cur) -> list[tuple[str, str]]:
    """Every node that has at least one child (is a to_item_id somewhere)
    but is NOT itself a child of anything (never appears as a from_item_id
    in a parent_of edge). This is the actual top of each tree in the
    forest — DFS from each of these covers every node in the current
    hierarchy exactly once, unlike find_staple_roots() above, which can
    print the same subtree twice (once on its own, once nested under a
    higher staple that is also its parent — see the Basmati Pilaf example
    in DESIGN.md)."""
    cur.execute(
        """
        SELECT DISTINCT m.id, m.name
        FROM item_relationships r
        JOIN menu_items m ON m.id = r.to_item_id
        WHERE r.relationship_type = 'parent_of'
          AND m.id NOT IN (
              SELECT from_item_id FROM item_relationships WHERE relationship_type = 'parent_of'
          )
        ORDER BY m.name
        """
    )
    return cur.fetchall()


def find_staple_roots(cur) -> list[tuple[str, str]]:
    """Staple dishes (is_staple=true) that are actually a parent of
    something in the current tree — i.e. worth using as a DFS starting
    point, not every staple in the catalog."""
    cur.execute(
        """
        SELECT DISTINCT m.id, m.name
        FROM item_relationships r
        JOIN menu_items m ON m.id = r.to_item_id
        WHERE r.relationship_type = 'parent_of' AND m.is_staple = true
        ORDER BY m.name
        """
    )
    return cur.fetchall()


def render_full_forest(cur) -> str:
    """Every tree in the current forest, each true root walked exactly
    once — the full, non-redundant hierarchy as it stands right now."""
    cur.execute("SELECT count(*) FROM menu_items")
    (item_count,) = cur.fetchone()
    cur.execute("SELECT count(*) FROM item_relationships WHERE relationship_type = 'parent_of'")
    (edge_count,) = cur.fetchone()

    roots = find_true_roots(cur)
    lines = [
        f"# Dish hierarchy — DFS snapshot ({date.today().isoformat()})",
        "",
        f"- {item_count} menu items loaded",
        f"- {edge_count} parent_of edges",
        f"- {len(roots)} root nodes in the current forest",
        "",
        "```",
    ]
    for root_id, root_name in roots:
        lines.extend(dfs(cur, root_id, root_name))
        lines.append("")
    lines.append("```")
    return "\n".join(lines)


def _mermaid_safe_label(name: str) -> str:
    """Mermaid flowchart node labels are wrapped in ["..."] — escape the one
    character that actually breaks that (a literal double quote); commas,
    parens, &, /, apostrophes are all fine inside it."""
    return name.replace('"', "'")


def render_mermaid(cur) -> str:
    """The full forest as a Mermaid flowchart (`graph TD`) — GitHub renders
    this natively inside a ```mermaid fenced block, no image file needed."""
    cur.execute(
        """
        SELECT c.id, c.name, p.id, p.name
        FROM item_relationships r
        JOIN menu_items c ON c.id = r.from_item_id
        JOIN menu_items p ON p.id = r.to_item_id
        WHERE r.relationship_type = 'parent_of'
        ORDER BY p.name, c.name
        """
    )
    edges = cur.fetchall()

    # Mermaid node ids must be simple tokens, not the dishes' real uuids
    # with hyphens (hyphens are fine, but keeping this independent of the
    # id format is safer) — assign short n0, n1, ... ids per distinct dish.
    node_id = {}

    def get_node_id(real_id: str, name: str) -> str:
        if real_id not in node_id:
            node_id[real_id] = f"n{len(node_id)}"
        return node_id[real_id]

    lines = ["```mermaid", "graph TD"]
    for child_id, child_name, parent_id, parent_name in edges:
        p = get_node_id(parent_id, parent_name)
        c = get_node_id(child_id, child_name)
        lines.append(f'    {p}["{_mermaid_safe_label(parent_name)}"] --> {c}["{_mermaid_safe_label(child_name)}"]')
    lines.append("```")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        help="Write the full-forest DFS snapshot to this file (markdown) instead of printing staple-rooted subtrees to stdout.",
    )
    parser.add_argument(
        "--mermaid",
        help="Write a Mermaid flowchart diagram of the full forest to this file (renders natively on GitHub).",
    )
    args = parser.parse_args()

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/madras_menu_local"
    )
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        if args.mermaid:
            cur.execute("SELECT count(*) FROM menu_items")
            (item_count,) = cur.fetchone()
            cur.execute("SELECT count(*) FROM item_relationships WHERE relationship_type = 'parent_of'")
            (edge_count,) = cur.fetchone()
            content = (
                f"# Dish hierarchy — diagram ({date.today().isoformat()})\n\n"
                f"{item_count} menu items loaded, {edge_count} parent_of edges.\n\n"
                + render_mermaid(cur)
            )
            with open(args.mermaid, "w") as f:
                f.write(content + "\n")
            print(f"Wrote Mermaid diagram to {args.mermaid}")
            return

        if args.out:
            content = render_full_forest(cur)
            with open(args.out, "w") as f:
                f.write(content + "\n")
            print(f"Wrote full-forest DFS snapshot to {args.out}")
            return

        roots = find_staple_roots(cur)
        print(f"{len(roots)} staple dishes are a parent of something in the current tree:\n")
        for root_id, root_name in roots:
            for line in dfs(cur, root_id, root_name):
                print(line)
            print()


if __name__ == "__main__":
    main()
