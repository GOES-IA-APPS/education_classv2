from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import SubjectCatalog, User
from app.repositories.subjects import (
    SUBJECT_LIST_OPTIONS,
    get_subject_catalog_by_id,
    list_subject_catalogs,
    save_subject_catalog,
)
from app.schemas.phase3 import SubjectCatalogCreate
from app.services.access_service import visible_subject_catalogs_stmt


def search_subject_catalogs(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    q: str | None = None,
) -> list[SubjectCatalog]:
    stmt = visible_subject_catalogs_stmt(db, current_user).options(*SUBJECT_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(SubjectCatalog.school_code == school_code)
    if academic_year:
        stmt = stmt.where(SubjectCatalog.academic_year == academic_year)
    if grade_label:
        stmt = stmt.where(SubjectCatalog.grade_label == grade_label)
    if q:
        stmt = stmt.where(
            (SubjectCatalog.subject_code.ilike(f"%{q}%"))
            | (SubjectCatalog.subject_name.ilike(f"%{q}%"))
        )
    return list_subject_catalogs(db, stmt)


def get_subject_catalog_detail(db: Session, current_user: User, subject_catalog_id: int) -> SubjectCatalog | None:
    return db.scalar(
        visible_subject_catalogs_stmt(db, current_user)
        .options(*SUBJECT_LIST_OPTIONS)
        .where(SubjectCatalog.id == subject_catalog_id)
    )


def create_subject_catalog_record(db: Session, payload: SubjectCatalogCreate) -> SubjectCatalog:
    return save_subject_catalog(db, payload)
