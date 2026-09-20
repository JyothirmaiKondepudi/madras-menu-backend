from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from embeddings.schema import EmbeddingOut, SearchResult
from embeddings.service import embed_menu_item, search_similar
from auth.dependencies import require_permission

router = APIRouter()

# Internal ETL/pipeline tooling, not client-facing — gated by a single
# "embedding:manage" permission, same idea as the hierarchy routes.

_manage = Depends(require_permission("embedding:manage"))


@router.post("/menu-items/{item_id}/embedding", response_model=EmbeddingOut, dependencies=[_manage])
def create_embedding(item_id: str, db: Session = Depends(get_db)):
    result = embed_menu_item(db, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="menu item not found")
    return result


@router.get("/embeddings/search", response_model=list[SearchResult], dependencies=[_manage])
def search_embeddings(
    text: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return search_similar(db, text, limit)
