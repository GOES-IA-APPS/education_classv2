from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GradeCatalog, ModalityCatalog, SectionCatalog, StudentEnrollment, TeacherAssignment, User
from app.repositories.catalogs import (
    list_grade_catalogs,
    list_modality_catalogs,
    list_section_catalogs,
    save_grade_catalog,
    save_modality_catalog,
    save_section_catalog,
)
from app.schemas.academic import GradeCatalogCreate, ModalityCatalogCreate, SectionCatalogCreate
from app.services.access_service import (
    visible_assignments_stmt,
    visible_enrollments_stmt,
    visible_grade_catalogs_stmt,
    visible_modality_catalogs_stmt,
    visible_section_catalogs_stmt,
)

DERIVED_CATALOG_LIMIT = 200


def list_manual_grade_catalogs(db: Session, current_user: User) -> list[GradeCatalog]:
    return list_grade_catalogs(db, visible_grade_catalogs_stmt(db, current_user))


def list_manual_section_catalogs(db: Session, current_user: User) -> list[SectionCatalog]:
    return list_section_catalogs(db, visible_section_catalogs_stmt(db, current_user))


def list_manual_modality_catalogs(db: Session, current_user: User) -> list[ModalityCatalog]:
    return list_modality_catalogs(db, visible_modality_catalogs_stmt(db, current_user))


def derive_grade_catalog_view(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
) -> list[dict]:
    rows: set[tuple[str | None, int | None, str]] = set()
    assignment_stmt = visible_assignments_stmt(db, current_user).where(TeacherAssignment.grade_label.is_not(None))
    enrollment_stmt = visible_enrollments_stmt(db, current_user).where(StudentEnrollment.grade_label.is_not(None))
    if school_code:
        assignment_stmt = assignment_stmt.where(TeacherAssignment.school_code == school_code)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.school_code == school_code)
    if academic_year:
        assignment_stmt = assignment_stmt.where(TeacherAssignment.academic_year == academic_year)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.academic_year == academic_year)
    for row in db.execute(
        assignment_stmt.with_only_columns(
            TeacherAssignment.school_code,
            TeacherAssignment.academic_year,
            TeacherAssignment.grade_label,
        )
    ):
        rows.add((row[0], row[1], row[2]))
    for row in db.execute(
        enrollment_stmt.with_only_columns(
            StudentEnrollment.school_code,
            StudentEnrollment.academic_year,
            StudentEnrollment.grade_label,
        )
    ):
        rows.add((row[0], row[1], row[2]))
    return [
        {"school_code": school, "academic_year": year, "grade_label": grade}
        for school, year, grade in sorted(rows, key=lambda item: ((item[1] or 0) * -1, item[0] or "", item[2]))
    ][:DERIVED_CATALOG_LIMIT]


def derive_section_catalog_view(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
) -> list[dict]:
    rows: set[tuple[str | None, int | None, str | None, str | None, str | None, str | None]] = set()
    assignment_stmt = visible_assignments_stmt(db, current_user)
    enrollment_stmt = visible_enrollments_stmt(db, current_user)
    if school_code:
        assignment_stmt = assignment_stmt.where(TeacherAssignment.school_code == school_code)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.school_code == school_code)
    if academic_year:
        assignment_stmt = assignment_stmt.where(TeacherAssignment.academic_year == academic_year)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.academic_year == academic_year)
    if grade_label:
        assignment_stmt = assignment_stmt.where(TeacherAssignment.grade_label == grade_label)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.grade_label == grade_label)
    for row in db.execute(
        assignment_stmt.with_only_columns(
            TeacherAssignment.school_code,
            TeacherAssignment.academic_year,
            TeacherAssignment.grade_label,
            TeacherAssignment.section_id,
            TeacherAssignment.section_name,
            TeacherAssignment.shift,
        )
    ):
        rows.add((row[0], row[1], row[2], row[3], row[4], row[5]))
    for row in db.execute(
        enrollment_stmt.with_only_columns(
            StudentEnrollment.school_code,
            StudentEnrollment.academic_year,
            StudentEnrollment.grade_label,
            StudentEnrollment.section_code,
            StudentEnrollment.section_code,
            None,
        )
    ):
        rows.add((row[0], row[1], row[2], row[3], row[4], row[5]))
    cleaned = [row for row in rows if row[3] or row[4]]
    return [
        {
            "school_code": school,
            "academic_year": year,
            "grade_label": grade,
            "section_code": section_code,
            "section_name": section_name,
            "shift": shift,
        }
        for school, year, grade, section_code, section_name, shift in sorted(
            cleaned,
            key=lambda item: ((item[1] or 0) * -1, item[0] or "", item[2] or "", item[3] or "", item[4] or ""),
        )
    ][:DERIVED_CATALOG_LIMIT]


def derive_modality_catalog_view(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
) -> list[dict]:
    rows: set[tuple[str | None, int | None, str, str | None]] = set()
    stmt = visible_enrollments_stmt(db, current_user).where(StudentEnrollment.modality.is_not(None))
    if school_code:
        stmt = stmt.where(StudentEnrollment.school_code == school_code)
    if academic_year:
        stmt = stmt.where(StudentEnrollment.academic_year == academic_year)
    for row in db.execute(
        stmt.with_only_columns(
            StudentEnrollment.school_code,
            StudentEnrollment.academic_year,
            StudentEnrollment.modality,
            StudentEnrollment.submodality,
        )
    ):
        rows.add((row[0], row[1], row[2], row[3]))
    return [
        {
            "school_code": school,
            "academic_year": year,
            "modality": modality,
            "submodality": submodality,
        }
        for school, year, modality, submodality in sorted(
            rows,
            key=lambda item: ((item[1] or 0) * -1, item[0] or "", item[2], item[3] or ""),
        )
    ][:DERIVED_CATALOG_LIMIT]


def create_grade_catalog_record(db: Session, payload: GradeCatalogCreate) -> GradeCatalog:
    return save_grade_catalog(db, payload)


def create_section_catalog_record(db: Session, payload: SectionCatalogCreate) -> SectionCatalog:
    return save_section_catalog(db, payload)


def create_modality_catalog_record(db: Session, payload: ModalityCatalogCreate) -> ModalityCatalog:
    return save_modality_catalog(db, payload)
