from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role


def get_role_by_code(db: Session, code: str) -> Role | None:
    return db.scalar(select(Role).where(Role.code == code))


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.name)).all())
