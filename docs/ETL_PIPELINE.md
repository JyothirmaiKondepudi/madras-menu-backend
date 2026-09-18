# The hierarchy ETL pipeline

Moved out of the main `README.md` on purpose — this is the detailed, elaborate reference for how dishes actually get classified into the tree; the main README keeps only a short pointer here. Two versions are documented below: the **manual pipeline** (how every edge currently in the database was actually produced, up through 682 items) and the **embedding-driven pipeline** (the design being built now, to automate the rest). Nothing in the manual version becomes wrong once the automated version exists — they're the same six conceptual stages, differing in how "Classify" actually happens.

## Version 1 — manual (how the tree got to 682 items / 88 edges)

```mermaid
graph TD
    A["Fetch new batch<br/>~150 items from the live catalog"] --> B["Dedupe<br/>exact-match duplicates set aside"]
    B --> C["Classify<br/>LLM proposes each item's parent"]
    C --> D["Validate<br/>reject unknown ids, cycles, self-parents"]
    D --> E["Human review<br/>read the report, catch reasoning mistakes"]
    E --> F["Apply<br/>insert_edge / update_edge writes it in"]
    F -.->|repeats per batch| A
```

"Classify" here was Claude reasoning directly over each batch's real dish names in a coding session — no API call, no model, just a person (an LLM acting as one) reading the list and proposing edges. That's why it doesn't scale past a few hundred items per session, and why the embedding-driven version below exists.

## Version 2 — embedding-driven (the design being built now)

Every stage below maps to a real FastAPI endpoint or a specific function — nothing here is hypothetical naming, this is the actual API surface.

```mermaid
flowchart TD
    A["Fetch new batch<br/>from the live catalog"] -->|"POST /menu-items"| B["Dedupe<br/>exact-match duplicates set aside"]
    B --> C["Generate embedding<br/>Ollama: nomic-embed-text"]
    C -->|"POST /menu-items/{id}/embedding"| D[("menu_item_embeddings<br/>table")]
    D --> E["Semantic search<br/>top-K similar existing dishes"]
    E -->|"GET /embeddings/search"| F["Candidate parent(s)<br/>retrieved by similarity"]
    F --> G["Classify<br/>LangChain agent + Ollama reasons over candidates"]
    G --> H["Proposal: parent_id or root<br/>+ reason + confidence"]
    H --> I{"Human review"}
    I -->|rejected| Z["Discard<br/>no write"]
    I -->|approved| J{"Already has<br/>a parent edge?"}
    J -->|no — new| K["POST /item-relationships"]
    J -->|yes — reclassify| L["PATCH /item-relationships/{child_id}"]
    K --> M["Node check<br/>do child_id & parent_id exist?"]
    L --> M
    M -->|fail| X["400 HierarchyError"]
    M -->|pass| N["Self-parent check<br/>child_id != parent_id"]
    N -->|fail| X
    N -->|pass| O["Cycle check<br/>walk the ancestor chain"]
    O -->|fail| X
    O -->|pass| P[("item_relationships<br/>row written")]
```

### Stage by stage

**1. Fetch new batch** — pull real dishes not yet loaded from the live catalog (`https://madras-menu-studio.vercel.app/api/menu-items`), create them via `POST /menu-items` (`routes/menu_items.py`) rather than a raw bulk `INSERT`, so every dish enters the system through the same validated path.

**2. Dedupe** — `hierarchy/dedupe.py`'s `find_duplicate_clusters()`. Case/whitespace-only duplicate names (`"Aloo baingan masala"` vs `"Aloo Baingan Masala"`) are grouped and only one representative per cluster proceeds. Local, deterministic, no LLM call, no DB write.

**3. Generate embedding** — for each item needing classification, build its embedding text (`name + course + cuisine_tags`, e.g. `"Tamarind rice (rice_biryani, south_indian, tamil, telugu_andhra)"`) and call Ollama's local embedding API (`nomic-embed-text`, 768-dimensional vectors) via `POST /menu-items/{id}/embedding`.

**4. Store embedding** — the vector is upserted into `menu_item_embeddings` — a brand-new table, added to Alembic's `OWNED_TABLES`, with zero changes to `menu_items` itself (see the main README's "Schema ownership" section for why that boundary matters).

**5. Semantic search** — `GET /embeddings/search?text=...` embeds the query text the same way, then runs a `pgvector` similarity query (`ORDER BY embedding <=> query_embedding`) against `menu_item_embeddings`, returning the top-K closest existing dishes. This is what correctly matches something like `"Tamarind infused rice with roasted peanuts and cashews and tempering"` to the real `Tamarind rice` row, despite zero shared vocabulary — a plain keyword search would miss that connection entirely.

**6. Classify** — a LangChain agent (Ollama as the underlying model) reasons over the retrieved candidates — not a fixed static list, actual retrieved matches — and proposes a `parent_id` (or `"root"`), with a `reason` and `confidence`, same output shape `hierarchy/schema.py` has always defined.

**7. Human review** — unchanged in spirit from Version 1: nothing gets written without a person looking at the proposal first. A rejected proposal is simply discarded; nothing about the tree changes.

**8. New edge vs. reclassification** — an approved proposal for an item that has no existing parent goes through `POST /item-relationships`; one for an item being *reclassified* (already has a parent, like the `Basmati Pilaf` → `Basmati rice` case) goes through `PATCH /item-relationships/{child_id}` instead. Both routes call into the same `hierarchy/mutations.py` functions underneath (`insert_edge` / `update_edge`).

**9. Node check** — `_item_exists()` in `hierarchy/mutations.py`: both `child_id` and `parent_id` must be real rows in `menu_items`, or the request fails with a `HierarchyError`, turned into a `400` by `main.py`'s global exception handler.

**10. Self-parent check** — `child_id == parent_id` is rejected outright, same handler.

**11. Cycle check** — `_would_create_cycle()`: walks the proposed parent's own ancestor chain; if the child being classified shows up anywhere in it, the write is rejected. This is the one rule Postgres itself has no way to enforce as a constraint (see the main README's note on why raw SQL against `item_relationships` is deliberately avoided) — it only exists in this application-level check.

**12. Write** — only after all three checks pass does a row actually get written to `item_relationships`.

## API endpoints referenced above

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/menu-items` | create a dish record |
| `POST` | `/menu-items/{id}/embedding` | generate + store an embedding for one dish |
| `GET` | `/embeddings/search` | semantic search for candidate parents |
| `POST` | `/item-relationships` | create a new `parent_of` edge |
| `PATCH` | `/item-relationships/{child_id}` | reclassify — change an existing edge's parent |
| `DELETE` | `/item-relationships/{child_id}` | remove one edge (item becomes a root) |
| `DELETE` | `/item-relationships/nodes/{item_id}` | remove an item from the hierarchy entirely, reparenting its children |

The last three already exist and are tested (`tests/test_item_relationships.py`); `/menu-items/{id}/embedding` and `/embeddings/search` are the two new ones this design calls for.

## Current status

`menu_item_embeddings` is real — created via a genuine Alembic migration (`alembic/versions/4821e0dd3b67_...py`), verified with an actual `pgvector` similarity query (not just a structure check), then emptied back out since that test row wasn't a real embedding. `embeddings/model.py` holds the SQLAlchemy model. One real bug caught along the way, worth remembering: Alembic's autogenerate referenced the `Vector` column type without importing it in the generated migration file — a known gap with custom column types — caught by reading the diff before applying it, not by running it and hoping.

**Database setup is now complete**, beyond the bare table:
- An **HNSW index** (`menu_item_embeddings_hnsw_cosine`, `vector_cosine_ops`) on the `embedding` column — pgvector 0.8.6 is installed, well past what HNSW needs. HNSW specifically (not IVFFlat) because it builds incrementally as rows are inserted, so it's fine to create on the currently-empty table rather than needing a representative sample of real vectors upfront the way IVFFlat does. `vector_cosine_ops` matches the `<=>` operator the search query actually uses — an index built with the wrong ops class silently never gets used by a query using a different distance operator.
- A **`menu_item_embeddings_readable` view**, joining a dish's embedding to its *current* tree parent (via `item_relationships`) — the "store `parent_id` directly in the embedding table" idea was deliberately rejected (see the main README) precisely because it would duplicate the one place the tree's structure is allowed to live; this view gets the same convenience live, with no duplicated/staleable data. Verified with `Chicken Biryani` → correctly resolves to its real parent, `Basmati rice`.

**`embeddings/service.py` and `embeddings/routes.py` are now written** — `POST /menu-items/{item_id}/embedding` and `GET /embeddings/search` both exist, using `langchain_ollama.OllamaEmbeddings` (`nomic-embed-text`) as designed. Ollama still isn't installed on this machine, though, so what's actually verified vs. not is worth being precise about:

- **Verified for real**: the 404 path (unknown item_id, checked before any Ollama call happens at all), and — genuinely useful — the *graceful failure* path. Calling either endpoint with Ollama unreachable was actually triggered (not guessed at) and raises a plain `builtins.ConnectionError`; `main.py` now has a specific handler for it (503, clear message), instead of falling through to the generic 500. Three tests in `tests/test_embeddings.py` cover exactly this, and pass without needing Ollama running at all.
- **Not yet verified**: the actual generate → store → search round trip, `upsert_embedding`'s `ON CONFLICT DO UPDATE` behavior, and `search_similar`'s query-row parsing on a real result set. None of this can be proven until Ollama is installed and pulled (`ollama pull nomic-embed-text`, `ollama pull llama3.1:8b`).

One real bug this surfaced along the way, now fixed properly (not just patched by hand): `madras_menu_test` never had the `pgvector` extension enabled (only `madras_menu_local` gets it automatically, via the Docker init script at first container boot) — `tests/conftest.py`'s `engine` fixture now runs `CREATE EXTENSION IF NOT EXISTS vector` before `Base.metadata.create_all()`, so this can't silently break again for anyone (including CI) starting from a fresh test database.
