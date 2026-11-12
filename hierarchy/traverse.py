"""Depth-first traversal of the item_relationships tree, from a given root down
through its parent_of children. Cycle-safe via a visited set, as a backstop."""

import argparse
import os
from datetime import date

import psycopg2


def get_children(cur, parent_id: str) -> list[tuple[str, str]]:
    """Direct children of parent_id as (id, name) pairs."""
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
    """Returns the subtree rooted at root_id as indented lines."""
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
    """Nodes with at least one child but no parent of their own — the actual top
    of each tree in the forest. Unlike find_staple_roots(), DFS from these covers
    every node exactly once."""
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
    """Staple dishes that are actually a parent of something in the current tree."""
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
    """Every tree in the current forest, each true root walked exactly once."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        help="Write the full-forest DFS snapshot to this file (markdown) instead of printing staple-rooted subtrees to stdout.",
    )
    args = parser.parse_args()

    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/madras_menu_local"
    )
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
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
