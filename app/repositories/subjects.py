from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import School, SubjectCatalog
from app.schemas.phase3 import SubjectCatalogCreate

SUBJECT_LIST_OPTIONS = (
    joinedload(SubjectCatalog.school),
)


def subject_catalog_list_stmt():
    return select(SubjectCatalog).options(*SUBJECT_LIST_OPTIONS)


def get_subject_catalog_by_id(db: Session, subject_catalog_id: int) -> SubjectCatalog | None:
    return db.scalar(subject_catalog_list_stmt().where(SubjectCatalog.id == subject_catalog_id))


def list_subject_catalogs(db: Session, stmt, limit: int = 200) -> list[SubjectCatalog]:
    return list(
        db.scalars(
            stmt.order_by(
                SubjectCatalog.academic_year.desc(),
                SubjectCatalog.grade_label,
                SubjectCatalog.display_order,
                SubjectCatalog.subject_name,
            ).limit(limit)
        ).all()
    )


def save_subject_catalog(db: Session, payload: SubjectCatalogCreate) -> SubjectCatalog:
    if payload.school_code and not db.get(School, payload.school_code):
        raise ValueError("La escuela indicada no existe.")

    subject = db.scalar(
        select(SubjectCatalog).where(
            SubjectCatalog.school_code == payload.school_code,
            SubjectCatalog.academic_year == payload.academic_year,
            SubjectCatalog.grade_label == payload.grade_label,
            SubjectCatalog.subject_code == payload.subject_code,
        )
    )
    if not subject:
        subject = SubjectCatalog(
            school_code=payload.school_code,
            academic_year=payload.academic_year,
            grade_label=payload.grade_label,
            subject_code=payload.subject_code,
        )
        db.add(subject)
    subject.subject_name = payload.subject_name
    subject.display_order = payload.display_order
    subject.source_type = "manual"
    subject.is_active = True
    db.commit()
    db.refresh(subject)
    return subject
