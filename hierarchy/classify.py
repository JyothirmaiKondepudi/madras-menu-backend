"""
The actual "Classify" stage from docs/ETL_PIPELINE.md Version 2 — a real
model call, not a person reasoning over the list by hand like the original
88-edge manual batches. One call per dish: retrieve candidates
(candidates.py), prompt the model to pick one or propose root
(classify_prompt.py), get back structured JSON (not regex-scraped free
text) matching hierarchy/schema.py's per-item shape.

Two providers, picked via CLASSIFICATION_PROVIDER, sharing everything else
(prompt, schema, validation) — this is exactly the provider-agnostic split
hierarchy/schema.py's docstring already called for:
  - "ollama": fully local, free, but this dev machine only has 8GB of
    unified memory. Even llama3.2:3b (~2GB) risked hanging the whole
    system once Docker (needed for the DB) and Chrome (the user needs it
    open) were both already running — see the real timeout/hang this
    surfaced with llama3.1:8b, which is why this module defaults to Gemini
    instead of trying to force the local path on hardware that can't fit
    it.
  - "gemini": a real API call (Gemini 2.5 Flash), no local RAM cost at
    all — the practical choice on this machine. Requires GEMINI_API_KEY
    (or GOOGLE_API_KEY) in the environment.
"""

import os
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from hierarchy.candidates import find_candidate_parents
from hierarchy.classify_prompt import build_item_prompt

CLASSIFICATION_PROVIDER = os.environ.get("CLASSIFICATION_PROVIDER", "gemini")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("CLASSIFICATION_MODEL", "llama3.2:3b")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


class ParentProposal(BaseModel):
    parent_id: str | None = Field(
        description="One of the candidate dish ids, or null if this dish is a root."
    )
    reason: str = Field(description="One short sentence justifying the proposed parent or root.")
    confidence: Literal["high", "medium", "low"]


def _build_structured_classifier():
    if CLASSIFICATION_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # thinking_budget=0 disables the model's extended-reasoning mode —
        # this task (pick one of ~8 candidates) doesn't need multi-step
        # reasoning, and thinking was the likely cause of the wide,
        # sometimes 60+ second per-call latency seen in the first real
        # smoke test.
        model = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0, thinking_budget=0)
    elif CLASSIFICATION_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        # num_ctx capped well below the model's default — a large default
        # forces a bigger KV-cache allocation on load, which is what made
        # the first-ever local call here time out ("timed out waiting for
        # llama-server to start"). Our prompts (one dish + ~8 candidates)
        # never come close to needing more than a few thousand tokens.
        model = ChatOllama(
            model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0, num_ctx=4096
        )
    else:
        raise ValueError(f"unknown CLASSIFICATION_PROVIDER: {CLASSIFICATION_PROVIDER!r}")
    return model.with_structured_output(ParentProposal)


_structured_classifier = _build_structured_classifier()


class ClassificationError(Exception):
    """The model proposed a parent_id that isn't one of the candidates it
    was given — treated as a rejected proposal, never silently coerced."""


def classify_item(db: Session, item: dict, k: int = 8) -> dict:
    """item: {id, name, course, cuisine_tags}. Returns a proposal dict
    matching hierarchy/schema.py's per-proposal shape: item_id, parent_id,
    reason, confidence, plus candidate_ids for validation/debugging."""
    candidates = find_candidate_parents(db, item["id"], k=k)
    candidate_ids = {c["id"] for c in candidates}

    prompt = build_item_prompt(item, candidates)
    result: ParentProposal = _structured_classifier.invoke(prompt)

    if result.parent_id is not None and result.parent_id not in candidate_ids:
        raise ClassificationError(
            f"model proposed parent_id {result.parent_id!r} for {item['id']!r}, "
            f"which isn't one of the {len(candidates)} candidates it was given"
        )

    return {
        "item_id": item["id"],
        "parent_id": result.parent_id,
        "reason": result.reason,
        "confidence": result.confidence,
        "candidate_ids": sorted(candidate_ids),
    }
