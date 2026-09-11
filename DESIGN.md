# Madras Menu Backend — Design

Status as of 2026-09-11: local-first hierarchy prototype built and validated against real (seed-scale) data. No GCP infra, no FastAPI service, no production database writes yet. Read this alongside the original "Revised Architecture" doc (pasted into chat during the session that started this repo, not yet copied here verbatim) — this file tracks what's actually been decided and built since, and supersedes that doc wherever the two disagree.

## What this repo is

The new Python backend for Madras Menu Studio's rewrite. The existing app (`madras-menu-studio`, Next.js/Prisma/TypeScript) is being superseded by a ground-up rewrite: a multi-tenant SaaS template for catering (other verticals like construction later), full CRM scope, FastAPI backend, Postgres with pgvector on GCP, knowledge-graph + embeddings-driven menu generation. This repo is where that new backend's code lives, separate from the old repo — per the business owner's own framing, the old repo's business logic (`src/server/**`) is expected to become redundant.

**What did NOT come over from `madras-menu-studio`:** `menu_etl_pipeline.py` (the dish-extraction pipeline) stays in the old repo for now — a deliberate scoping choice made when this repo was created, not an oversight. It may move here later.

## Target architecture (business direction, confirmed by the owner)

- Multi-tenant: any catering company can run their own instance.
- Multi-domain: catering first, other verticals later, via a domain-agnostic foundation.
- Beyond menu generation: full CRM (project/event management, invoicing, multiple user portals).
- Menu generation becomes knowledge-graph + embeddings driven (RAG-style), replacing the old app's flat rule-based `MenuGenerator.ts`.
- Stack: FastAPI (Python), Postgres on GCP (Cloud SQL vs. AlloyDB not yet decided), pgvector, Gemini for embeddings, React/Next.js frontend kept but rehosted on GCP.

## The hierarchy / knowledge graph — design decided this session

The outside-engineer recommendation behind this ("every menu needs a decision tree," "generating a menu creates a new graph-like structure") was a confirmed *direction*, not a confirmed *design*, going into this session. Resolved:

- **Dishes are the graph's nodes.** An existing dish can relate to another dish directly — not a separate category-label taxonomy layered on top.
- **A generic edges table, not a dedicated `parentId` column**: `item_relationships(from_item_id, to_item_id, relationship_type, metadata)`. "Parent/child" is `relationship_type = 'parent_of'`. This is one substrate for both today's hierarchy and the later knowledge-graph's other relationship types (e.g. `pairs_with`), rather than building a tree now and a separate graph table later.
- **Single-parent-per-item, enforced as a partial unique index** (`UNIQUE (from_item_id) WHERE relationship_type = 'parent_of'`), not a schema-level constraint — relaxing to multi-parent later is a `DROP INDEX`, no data migration. Checked against real generated menu data before deciding this: the cases that look like they'd need two parents (fusion dishes blending two cuisines) are already handled by the existing multi-value `cuisineTags` field; no real item needed two independent dish-family lineages.
- **Cycle safety** isn't fully covered by the unique index (it stops a child getting two parents, not a longer A→B→A cycle) — enforced instead in the classification/validation step itself (see `hierarchy/validate.py`).
- **Exact duplicates are not a hierarchy relationship.** Case/whitespace-only duplicate dish names (a real problem in the live catalog — e.g. `"Aloo baingan masala"` vs `"Aloo Baingan Masala"`) are caught deterministically before any LLM call, not left to the LLM to notice, and are never written as `parent_of` edges — they're a separate merge/dedup concern (see `hierarchy/dedupe.py`).
- **Local-first.** All of this was designed and tested against a local Postgres (`madras_menu_local`, Postgres.app), seeded from the existing `madras-menu-studio` repo's own dev fixture (`prisma/seed-data/menu_items_seed.json`, 79 items) via `prisma db push`. The shared Neon/Supabase DB the live app runs on was never touched. GCP Cloud SQL provisioning is a distinct, later step — no GCP project exists yet as of this writing (billing setup is pending).

## Current status — what's actually built

- `hierarchy/schema.py` — the provider-agnostic JSON response shape every LLM call must produce: one proposal per dish (`item_id`, `parent_id` or `null`, `reason`, `confidence`).
- `hierarchy/prompt.py` — builds the classification prompt for a batch of items. Works today; not yet wired to any real API call.
- `hierarchy/dedupe.py` — case/whitespace-insensitive exact-duplicate detection, run *before* classification. Only one representative per duplicate cluster goes on to the LLM.
- `hierarchy/validate.py` — validates every proposal before it's trusted: unknown item/parent ids, self-parenting, and cycles (walks the full proposed-parent chain, so an item downstream of a broken cycle is correctly rejected too, not just the two nodes directly in it).
- `hierarchy/report.py` — renders a plain markdown report (valid edges, rejected proposals with why, duplicate clusters, items with no proposal) — this report **is** the review step right now, mirroring `madras-menu-studio`'s own draft → `/review` → promote pattern for menu items. Nothing gets written to any database from this code yet.
- `propose_hierarchy.py` — the entry point. `--dry-run` uses a small hardcoded fixture (including a deliberate mutual-cycle case, to prove `validate.py` actually rejects it — and correctly rejects everything downstream of it too). A real run (no `--dry-run`) reads from `DATABASE_URL` via `psycopg2`; `call_llm()` currently raises `NotImplementedError` — **no LLM provider is wired up yet.**

**How the first real batch actually got classified**: rather than waiting on GCP billing setup (in progress as of this writing) to wire up `call_llm()`, the 79 real seeded items were classified directly by Claude inline in a coding session — reading the real dish list, reasoning through parent/child candidates by hand, writing the result as a JSON proposals file, and running it through the *exact same* `validate_proposals`/`render_report` functions above. Zero API cost, proved the full pipeline end-to-end on real (if seed-scale) data. Result: 72 roots, 7 `parent_of` edges, 0 rejected, 0 duplicates found in this particular 79-item set. This doesn't scale to the real ~1,730+ item catalog (that needs an actual automated call — see below), but it validated the mechanism before spending any setup effort on a real provider integration.

## Next steps (not yet done)

- Wire a real provider into `call_llm()` — planned as Vertex AI (GCP credits, once billing is set up), Flash/Flash-Lite tier. The Anthropic API was also priced out as an option (~$0.02–0.12 for a 79-item batch on Haiku/Sonnet/Opus 5 respectively) and stays available if Vertex AI setup stalls.
- At real catalog scale (~1,730+ promoted items, thousands of drafts), the "send everyone the whole candidate list" prompt approach won't scale — needs candidate-narrowing (cheap text similarity, or real embeddings) before an LLM ever proposes a parent for a given item. Not built yet.
- Actually writing accepted `item_relationships` rows to a database (this code only ever produces a report today).
- The FastAPI service itself, and porting `MenuGenerator.ts`/`pricingService.ts`/`noRepeatLedger.ts` (the old repo's "Step 1," explicitly put on hold in favor of this hierarchy work).
- GCP infra (Cloud SQL vs. AlloyDB, pgvector), multi-tenancy, auth, frontend wiring, the ETL Claude→Gemini swap.
