from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from embeddings.schema import EmbeddingOut, SearchResult
from embeddings.service import embed_menu_item, search_similar
from auth.dependencies import require_admin

router = APIRouter()

# Internal ETL/pipeline tooling, not client-facing — admin-only, same as
# the hierarchy routes.


@router.post("/menu-items/{item_id}/embedding", response_model=EmbeddingOut)
def create_embedding(item_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    result = embed_menu_item(db, item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="menu item not found")
    return result


@router.get("/embeddings/search", response_model=list[SearchResult])
def search_embeddings(
    text: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return search_similar(db, text, limit)
