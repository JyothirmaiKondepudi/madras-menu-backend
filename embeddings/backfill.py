"""One-off bulk job: generate an embedding for every menu_items row that
doesn't have one yet in menu_item_embeddings. Not a route — this is meant
to be run from the command line (`python -m embeddings.backfill`), since a
run over ~1,450 dishes means ~1,450 sequential Ollama calls and has no
place being triggered by an HTTP request.

Reuses embed_menu_item() (the same function POST /menu-items/{id}/embedding
calls) so a single dish embedded via this script and one embedded via the
API are produced identically — no parallel code path to drift out of sync.
"""

import time

from sqlalchemy import select

from database import SessionLocal
from models import MenuItem
from embeddings.model import MenuItemEmbedding
from embeddings.service import embed_menu_item


def find_unembedded_item_ids(db) -> list[str]:
    return list(
        db.scalars(
            select(MenuItem.id).outerjoin(
                MenuItemEmbedding, MenuItemEmbedding.itemId == MenuItem.id
            ).where(MenuItemEmbedding.itemId.is_(None))
        )
    )


def run(batch_log_every: int = 25) -> None:
    db = SessionLocal()
    try:
        item_ids = find_unembedded_item_ids(db)
        total = len(item_ids)
        if total == 0:
            print("Nothing to do — every menu item already has an embedding.")
            return

        print(f"{total} menu items need embeddings. Starting…")
        started = time.monotonic()
        succeeded = 0
        failed: list[tuple[str, str]] = []

        for i, item_id in enumerate(item_ids, start=1):
            try:
                embed_menu_item(db, item_id)
                succeeded += 1
            except Exception as exc:  # noqa: BLE001 — one bad dish shouldn't kill a 1,450-item run
                db.rollback()
                failed.append((item_id, str(exc)))

            if i % batch_log_every == 0 or i == total:
                elapsed = time.monotonic() - started
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (total - i) / rate if rate > 0 else float("inf")
                print(
                    f"[{i}/{total}] ok={succeeded} failed={len(failed)} "
                    f"elapsed={elapsed:0.0f}s eta={remaining:0.0f}s",
                    flush=True,
                )

        print(f"\nDone. {succeeded}/{total} embedded, {len(failed)} failed.")
        if failed:
            print("Failed item ids:")
            for item_id, err in failed:
                print(f"  {item_id}: {err}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
