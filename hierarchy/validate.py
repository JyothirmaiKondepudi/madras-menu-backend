"""Validates proposed parent_of edges (item/parent existence, self-parenting,
cycles) before any of them get written."""

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
    missing_item_ids: list[str] = field(default_factory=list)


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
    """Walks the proposed parent chain from parent_id; if item_id (or any
    ancestor) reappears, returns the chain that proves the cycle."""
    chain = [item_id]
    current = parent_id
    seen = {item_id}
    max_steps = len(proposal_by_item) + 1

    for _ in range(max_steps):
        chain.append(current)
        if current in seen:
            return chain
        seen.add(current)

        next_proposal = proposal_by_item.get(current)
        if next_proposal is None:
            return None
        current = next_proposal.get("parent_id")
        if current is None:
            return None

    return chain
