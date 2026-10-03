"""Provider-agnostic response schema for hierarchy proposals: one entry per menu
item, with parent_id null meaning it's a root dish."""

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
