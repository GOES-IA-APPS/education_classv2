from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import School


def get_school_by_code(db: Session, code: str) -> School | None:
    return db.get(School, code)


def list_schools(db: Session) -> list[School]:
    return list(db.scalars(select(School).order_by(School.name)).all())
