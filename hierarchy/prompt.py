"""
Builds the single prompt sent to the LLM for the local prototype (all 79
seeded items at once — see the plan doc for why this doesn't need the
candidate-narrowing approach the full ~1,730+ item catalog will eventually
need).
"""

import json

INSTRUCTIONS = """\
You are helping build a hierarchy over a catering menu's dish catalog.

Below is the full list of dishes (id, name, course, cuisine tags). For EVERY
dish in the list, propose either:
  - a parent_id: the id of another dish in this same list that this one is
    a more specific variant of (e.g. "Hyderabadi Chicken Biryani" is a
    variant of "Chicken Biryani", which is itself a variant of "Basmati
    Rice"), or
  - null, if this dish is a root — not a meaningful variant of anything
    else in the list.

Rules:
- A dish's parent must be a genuinely broader/more general version of the
  same dish family (an "is a more specific version of" relationship) — not
  just something that shares a cuisine or is served alongside it. Cuisine
  overlap is already captured elsewhere and should NOT by itself justify a
  parent link.
- Never propose a dish as its own parent.
- Only propose parent_ids that appear in the list below.
- If you're unsure, prefer null (root) over a low-confidence guess — use
  "low" confidence rather than omitting a proposal.
- Every single dish in the list must get exactly one proposal.

Return your answer as JSON matching the required schema — one entry in
`proposals` per dish, in any order.

Dishes:
{items_json}
"""


def build_prompt(items: list[dict]) -> str:
    """items: list of {id, name, course, cuisine_tags} dicts."""
    compact = [
        {
            "id": item["id"],
            "name": item["name"],
            "course": item["course"],
            "cuisine_tags": item["cuisine_tags"],
        }
        for item in items
    ]
    return INSTRUCTIONS.format(items_json=json.dumps(compact, indent=2))
