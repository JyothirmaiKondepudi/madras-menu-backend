"""
The response shape every LLM provider must produce for the hierarchy
prototype. Kept provider-agnostic on purpose: Vertex AI's `response_schema`
param, Claude's tool-use input schema, or a hand-parsed JSON string from
anything else can all target this same structure — the validation and
report code in this package only ever sees plain dicts matching it, never
anything provider-specific.

One proposal per input MenuItem. `parent_id: null` means "this is a root
dish" (no parent_of edge gets written for it). See the plan doc
(~/.claude/plans/declarative-baking-cookie.md) for why this is a generic
edge shape rather than a dedicated parentId column.
"""

RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "The id of the dish this proposal is about.",
                    },
                    "parent_id": {
                        "type": ["string", "null"],
                        "description": (
                            "The id of the dish this one is a more specific "
                            "variant of, or null if this dish is a root "
                            "(not a variant of anything else in the list)."
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "One short sentence justifying the proposed parent (or root).",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": ["item_id", "parent_id", "reason", "confidence"],
            },
        }
    },
    "required": ["proposals"],
}
