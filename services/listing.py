"""Paging and sorting for every list endpoint (BE-08).

A list route builds its query (scoping and filters), then hands it to
paginate(), which sorts it, counts it and returns one page:

    {"items": [...], "total": 240, "limit": 50, "offset": 100}

limit defaults to 50 and is capped at 200, so no request reads a whole
table. sort is a field name, ascending, or with a leading "-" for
descending (?sort=-createdAt); each route lists the fields it allows.
"""

from typing import Annotated, Generic, TypeVar

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page(BaseModel, Generic[T]):
    items: list[T]
    # rows matching the filters, across all pages
    total: int
    limit: int
    offset: int


class ListParams:
    def __init__(
        self,
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
        sort: str | None = Query(
            None, description="a field name, or -field for descending"
        ),
    ):
        self.limit = limit
        self.offset = offset
        self.sort = sort


Listing = Annotated[ListParams, Depends()]


def paginate(
    db: Session,
    stmt: Select,
    params: ListParams,
    sorts: dict,
    default_sort: str,
    tiebreak,
) -> dict:
    """One page of stmt's rows. sorts maps the field names callers may sort
    by to columns; tiebreak (the primary key) keeps the order stable when
    the sort column has equal values, so rows don't repeat or go missing
    between pages."""
    key = params.sort or default_sort
    name = key.removeprefix("-")
    if name not in sorts:
        raise HTTPException(
            status_code=422,
            detail=f"Can't sort by {name!r}. Choose from: {', '.join(sorted(sorts))}.",
        )
    column = sorts[name]
    order = column.desc() if key.startswith("-") else column.asc()

    stmt = stmt.order_by(None)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        db.execute(
            stmt.order_by(order.nulls_last(), tiebreak)
            .limit(params.limit)
            .offset(params.offset)
        )
        .scalars()
        .unique()
        .all()
    )
    return {"items": rows, "total": total, "limit": params.limit, "offset": params.offset}
