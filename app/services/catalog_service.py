from __future__ import annotations

from sqlalchemy import String, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import GradeCatalog, ModalityCatalog, SectionCatalog, StudentEnrollment, TeacherAssignment, User
from app.repositories.catalogs import (
    delete_grade_catalog,
    get_grade_catalog_by_id,
    grade_catalogs_table_available,
    list_grade_catalogs,
    list_modality_catalogs,
    list_section_catalogs,
    save_grade_catalog,
    save_modality_catalog,
    save_section_catalog,
    update_grade_catalog,
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
    if not grade_catalogs_table_available(db):
        return []
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
    q: str | None = None,
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
    rows_list = [
        {"school_code": school, "academic_year": year, "grade_label": grade}
        for school, year, grade in sorted(rows, key=lambda item: ((item[1] or 0) * -1, item[0] or "", item[2]))
    ]
    if q:
        query = q.strip().lower()
        rows_list = [
            row
            for row in rows_list
            if query in (row["school_code"] or "").lower()
            or query in str(row["academic_year"] or "").lower()
            or query in (row["grade_label"] or "").lower()
        ]
    return rows_list[:DERIVED_CATALOG_LIMIT]


def search_grade_catalog_entries(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    q: str | None = None,
) -> tuple[list[dict], bool]:
    schools_stmt = visible_grade_catalogs_stmt(db, current_user)
    if school_code:
        schools_stmt = schools_stmt.where(GradeCatalog.school_code == school_code)
    if q:
        query = f"%{q.strip().lower()}%"
        schools_stmt = schools_stmt.where(
            or_(
                func.lower(func.coalesce(GradeCatalog.school_code, "")).like(query),
                func.lower(func.coalesce(GradeCatalog.grade_label, "")).like(query),
                func.lower(func.coalesce(GradeCatalog.display_name, "")).like(query),
                func.cast(GradeCatalog.academic_year, String).like(f"%{q.strip()}%"),
            )
        )

    manual_available = grade_catalogs_table_available(db)
    manual_rows = list_grade_catalogs(db, schools_stmt) if manual_available else []
    derived_rows = derive_grade_catalog_view(
        db,
        current_user,
        school_code=school_code,
        q=q,
    )

    rows = [
        {
            "id": grade.id,
            "source_type": "manual",
            "school_code": grade.school_code,
            "academic_year": grade.academic_year,
            "grade_label": grade.grade_label,
            "display_name": grade.display_name,
            "is_editable": True,
            "is_deletable": True,
        }
        for grade in manual_rows
    ]
    rows.extend(
        {
            "id": None,
            "source_type": "derived",
            "school_code": row["school_code"],
            "academic_year": row["academic_year"],
            "grade_label": row["grade_label"],
            "display_name": None,
            "is_editable": False,
            "is_deletable": False,
        }
        for row in derived_rows
    )
    rows.sort(
        key=lambda item: (
            -int(item["academic_year"] or 0),
            item["school_code"] or "",
            item["grade_label"] or "",
            item["source_type"],
        )
    )
    return rows, (not manual_available)


def get_grade_catalog_entry(
    db: Session,
    current_user: User,
    *,
    source_type: str,
    grade_id: int | None = None,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
) -> dict | None:
    if source_type == "manual":
        if not grade_catalogs_table_available(db) or grade_id is None:
            return None
        grade = get_grade_catalog_by_id(db, visible_grade_catalogs_stmt(db, current_user), grade_id)
        if not grade:
            return None
        return {
            "id": grade.id,
            "source_type": "manual",
            "school_code": grade.school_code,
            "academic_year": grade.academic_year,
            "grade_label": grade.grade_label,
            "display_name": grade.display_name,
            "is_editable": True,
            "is_deletable": True,
            "entity": grade,
        }

    for row in derive_grade_catalog_view(
        db,
        current_user,
        school_code=school_code,
        academic_year=academic_year,
    ):
        if (
            row["school_code"] == school_code
            and row["academic_year"] == academic_year
            and row["grade_label"] == grade_label
        ):
            return {
                "id": None,
                "source_type": "derived",
                "school_code": row["school_code"],
                "academic_year": row["academic_year"],
                "grade_label": row["grade_label"],
                "display_name": None,
                "is_editable": False,
                "is_deletable": False,
                "entity": None,
            }
    return None


def update_grade_catalog_record(
    db: Session,
    current_user: User,
    grade_id: int,
    payload: GradeCatalogCreate,
) -> GradeCatalog:
    if not grade_catalogs_table_available(db):
        raise ValueError("La tabla local de grados manuales no está disponible en esta base.")
    catalog = get_grade_catalog_by_id(db, visible_grade_catalogs_stmt(db, current_user), grade_id)
    if not catalog:
        raise ValueError("Grado manual no encontrado.")
    return update_grade_catalog(db, catalog, payload)


def delete_grade_catalog_record(db: Session, current_user: User, grade_id: int) -> None:
    if not grade_catalogs_table_available(db):
        raise ValueError("La tabla local de grados manuales no está disponible en esta base.")
    catalog = get_grade_catalog_by_id(db, visible_grade_catalogs_stmt(db, current_user), grade_id)
    if not catalog:
        raise ValueError("Grado manual no encontrado.")
    try:
        delete_grade_catalog(db, catalog.id)
    except SQLAlchemyError as exc:
        raise ValueError(
            "No se pudo eliminar el grado por integridad referencial o dependencias activas."
        ) from exc


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
    if not grade_catalogs_table_available(db):
        raise ValueError("La tabla local de grados manuales no está disponible en esta base.")
    return save_grade_catalog(db, payload)


def create_section_catalog_record(db: Session, payload: SectionCatalogCreate) -> SectionCatalog:
    return save_section_catalog(db, payload)


def create_modality_catalog_record(db: Session, payload: ModalityCatalogCreate) -> ModalityCatalog:
    return save_modality_catalog(db, payload)
