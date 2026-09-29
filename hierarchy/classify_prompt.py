"""
Per-item prompt for the retrieval-driven classify stage. Unlike prompt.py
(the whole-catalog version used for the original 79-item manual batches),
this only ever shows the model one dish plus its retrieved candidate
parents — the model picks a parent_id from THAT list, or null for root.
Keeping the candidate set closed (rather than "any id") makes the output
easy to validate: a hallucinated id is trivially caught, since it just
won't be in the candidates list we pass in.
"""

import json

INSTRUCTIONS = """\
You are extending a hierarchy over a catering menu's dish catalog. Each \
link means "is a more specific variant of" (e.g. "Hyderabadi Chicken \
Biryani" is a variant of "Chicken Biryani", which is a variant of \
"Basmati Rice") — NOT "is served with" or "shares a cuisine with".

Dish to classify:
{target_json}

Candidate parents (the {k} existing dishes most semantically similar to \
the dish above):
{candidates_json}

Pick ONE candidate's id as parent_id if the dish above is a genuinely more \
specific variant of it. Return parent_id: null if none of the candidates \
are a true broader/general version of this same dish — a related dish \
from the same cuisine or course is NOT by itself a reason to pick it.

Rules:
- parent_id must be exactly one of the candidate ids above, or null.
- Never invent an id that isn't in the candidates list.
- If unsure, prefer null (root) over a low-confidence guess, and mark it \
confidence: "low" rather than skipping the reason.
"""


def build_item_prompt(target: dict, candidates: list[dict]) -> str:
    """target: {id, name, course, cuisine_tags}. candidates: from
    candidates.find_candidate_parents (already includes current_parent_id
    for context, harmless if the model ignores it)."""
    target_compact = {
        "id": target["id"],
        "name": target["name"],
        "course": target["course"],
        "cuisine_tags": target.get("cuisine_tags") or [],
    }
    return INSTRUCTIONS.format(
        target_json=json.dumps(target_compact, indent=2),
        k=len(candidates),
        candidates_json=json.dumps(candidates, indent=2, default=str),
    )
