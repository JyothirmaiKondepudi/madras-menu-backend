"""
Provider-agnostic validation of proposed parent_of edges, before any of
them get written anywhere. This is the part that must never be skipped —
an LLM's raw proposals are untrusted until every one of these checks
passes. See the plan doc's cycle-safety note: a partial unique index in
Postgres stops a dish getting two parents, but it can't by itself stop a
longer cycle (A -> B -> A), so that check has to happen here instead.
"""

from dataclasses import dataclass, field


@dataclass
class Rejection:
    item_id: str
    parent_id: str | None
    reason: str


@dataclass
class ValidationResult:
    valid: list[dict] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    missing_item_ids: list[str] = field(default_factory=list)  # items with no proposal at all


def validate_proposals(items: list[dict], proposals: list[dict]) -> ValidationResult:
    item_ids = {item["id"] for item in items}
    proposal_by_item = {p["item_id"]: p for p in proposals}
    result = ValidationResult()

    result.missing_item_ids = sorted(item_ids - set(proposal_by_item.keys()))

    for proposal in proposals:
        item_id = proposal.get("item_id")
        parent_id = proposal.get("parent_id")

        if item_id not in item_ids:
            result.rejected.append(
                Rejection(item_id, parent_id, "proposal references an item_id not in the input list")
            )
            continue

        if parent_id is None:
            result.valid.append(proposal)
            continue

        if parent_id not in item_ids:
            result.rejected.append(
                Rejection(item_id, parent_id, "proposed parent_id is not in the input list")
            )
            continue

        if parent_id == item_id:
            result.rejected.append(Rejection(item_id, parent_id, "item proposed as its own parent"))
            continue

        cycle = _find_cycle(item_id, parent_id, proposal_by_item)
        if cycle:
            result.rejected.append(
                Rejection(item_id, parent_id, f"would create a cycle: {' -> '.join(cycle)}")
            )
            continue

        result.valid.append(proposal)

    return result


def _find_cycle(item_id: str, parent_id: str, proposal_by_item: dict) -> list[str] | None:
    """
    Walk the proposed parent chain starting at parent_id. If item_id shows
    up anywhere in that chain, accepting this proposal would create a
    cycle. Bounded by len(proposal_by_item) + 1 so a *pre-existing* bad
    cycle elsewhere in the proposals can't spin this into an infinite loop.
    """
    chain = [item_id]
    current = parent_id
    seen_in_chain = {item_id}
    max_steps = len(proposal_by_item) + 1

    for _ in range(max_steps):
        chain.append(current)
        if current in seen_in_chain:
            return chain  # cycle exists among the ancestors themselves, independent of item_id
        seen_in_chain.add(current)

        if current == item_id:
            return chain

        next_proposal = proposal_by_item.get(current)
        if next_proposal is None:
            return None  # chain ends at something with no proposal (shouldn't happen, but not our cycle)
        current = next_proposal.get("parent_id")
        if current is None:
            return None  # chain terminates at a root — no cycle

    return chain  # exceeded max_steps without terminating — treat as a cycle to be safe
