from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.utils.cache import build_cache_key, get_cache, set_cache
from app.utils.pagination import PaginationResult


def _ordered_identifiers(
    db: Session,
    *,
    stmt,
    id_column,
    order_by,
    page: int,
    per_page: int,
) -> list[Any]:
    offset = (page - 1) * per_page
    selected_columns = [id_column]
    selected_keys = {getattr(id_column, "key", str(id_column))}
    for expression in order_by:
        base_expression = getattr(expression, "element", expression)
        expression_key = getattr(base_expression, "key", str(base_expression))
        if expression_key in selected_keys:
            continue
        selected_columns.append(base_expression)
        selected_keys.add(expression_key)
    id_stmt = stmt.with_only_columns(*selected_columns).order_by(*order_by).offset(offset).limit(per_page)
    return [row[0] for row in db.execute(id_stmt).all()]


def _count_rows(db: Session, *, stmt, id_column) -> int:
    id_stmt = stmt.with_only_columns(id_column).order_by(None)
    return db.scalar(select(func.count()).select_from(id_stmt.subquery())) or 0


def paginate_entities(
    db: Session,
    *,
    base_stmt,
    fetch_stmt,
    id_column,
    order_by,
    page: int,
    per_page: int,
    cache_namespace: str,
    cache_scope: dict[str, Any],
) -> PaginationResult:
    meta_key = build_cache_key(
        f"{cache_namespace}:meta",
        scope={**cache_scope, "per_page": per_page},
    )
    total = get_cache(meta_key)
    if total is None:
        total = _count_rows(db, stmt=base_stmt, id_column=id_column)
        set_cache(meta_key, total)

    normalized_page = 1 if total == 0 else min(page, max(1, ((total - 1) // per_page) + 1))
    page_key = build_cache_key(
        f"{cache_namespace}:page",
        scope={**cache_scope, "page": normalized_page, "per_page": per_page},
    )
    identifiers = get_cache(page_key)
    if identifiers is None:
        identifiers = tuple(
            _ordered_identifiers(
                db,
                stmt=base_stmt,
                id_column=id_column,
                order_by=order_by,
                page=normalized_page,
                per_page=per_page,
            )
        )
        set_cache(page_key, identifiers)

    items = []
    if identifiers:
        attr_name = id_column.key
        positions = {identifier: index for index, identifier in enumerate(identifiers)}
        records = db.scalars(
            fetch_stmt.where(id_column.in_(identifiers)).order_by(*order_by)
        ).unique().all()
        items = sorted(records, key=lambda item: positions.get(getattr(item, attr_name), len(positions)))

    return PaginationResult(
        items=list(items),
        page=normalized_page,
        per_page=per_page,
        total=int(total),
    )
