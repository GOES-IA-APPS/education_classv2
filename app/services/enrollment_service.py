from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Student, StudentEnrollment, User
from app.repositories.enrollments import (
    ENROLLMENT_LIST_OPTIONS,
    get_enrollment_by_id,
    list_enrollments,
    save_enrollment,
)
from app.schemas.academic import StudentEnrollmentCreate
from app.services.pagination_service import paginate_entities
from app.services.access_service import visible_enrollments_stmt
from app.utils.cache import invalidate_namespace
from app.utils.pagination import DEFAULT_PER_PAGE, PaginationResult


def _enrollment_search_clause(q: str):
    query = f"%{q.strip().lower()}%"
    return or_(
        func.lower(func.coalesce(StudentEnrollment.nie, "")).like(query),
        func.lower(func.coalesce(StudentEnrollment.grade_label, "")).like(query),
        func.lower(func.coalesce(StudentEnrollment.section_code, "")).like(query),
        func.lower(func.coalesce(StudentEnrollment.modality, "")).like(query),
        func.lower(func.coalesce(StudentEnrollment.submodality, "")).like(query),
        StudentEnrollment.student.has(
            or_(
                func.lower(func.coalesce(Student.first_name1, "")).like(query),
                func.lower(func.coalesce(Student.first_name2, "")).like(query),
                func.lower(func.coalesce(Student.first_name3, "")).like(query),
                func.lower(func.coalesce(Student.last_name1, "")).like(query),
                func.lower(func.coalesce(Student.last_name2, "")).like(query),
                func.lower(func.coalesce(Student.last_name3, "")).like(query),
            )
        ),
    )


def search_enrollments(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    modality: str | None = None,
    submodality: str | None = None,
    nie: str | None = None,
    q: str | None = None,
) -> list[StudentEnrollment]:
    stmt = visible_enrollments_stmt(db, current_user).options(*ENROLLMENT_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(StudentEnrollment.school_code == school_code)
    if academic_year:
        stmt = stmt.where(StudentEnrollment.academic_year == academic_year)
    if grade_label:
        stmt = stmt.where(StudentEnrollment.grade_label == grade_label)
    if section_code:
        stmt = stmt.where(StudentEnrollment.section_code == section_code)
    if modality:
        stmt = stmt.where(StudentEnrollment.modality == modality)
    if submodality:
        stmt = stmt.where(StudentEnrollment.submodality == submodality)
    if nie:
        stmt = stmt.where(StudentEnrollment.nie == nie)
    if q:
        stmt = stmt.where(_enrollment_search_clause(q))
    return list_enrollments(db, stmt)


def search_enrollments_page(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    modality: str | None = None,
    submodality: str | None = None,
    nie: str | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> PaginationResult[StudentEnrollment]:
    base_stmt = visible_enrollments_stmt(db, current_user)
    if school_code:
        base_stmt = base_stmt.where(StudentEnrollment.school_code == school_code)
    if academic_year:
        base_stmt = base_stmt.where(StudentEnrollment.academic_year == academic_year)
    if grade_label:
        base_stmt = base_stmt.where(StudentEnrollment.grade_label == grade_label)
    if section_code:
        base_stmt = base_stmt.where(StudentEnrollment.section_code == section_code)
    if modality:
        base_stmt = base_stmt.where(StudentEnrollment.modality == modality)
    if submodality:
        base_stmt = base_stmt.where(StudentEnrollment.submodality == submodality)
    if nie:
        base_stmt = base_stmt.where(StudentEnrollment.nie == nie)
    if q:
        base_stmt = base_stmt.where(_enrollment_search_clause(q))
    fetch_stmt = base_stmt.options(*ENROLLMENT_LIST_OPTIONS)
    return paginate_entities(
        db,
        base_stmt=base_stmt,
        fetch_stmt=fetch_stmt,
        id_column=StudentEnrollment.id,
        order_by=(
            StudentEnrollment.academic_year.desc(),
            StudentEnrollment.school_code,
            StudentEnrollment.grade_label,
            StudentEnrollment.section_code,
            StudentEnrollment.id.desc(),
        ),
        page=page,
        per_page=per_page,
        cache_namespace="enrollments",
        cache_scope={
            "user_id": current_user.id,
            "role_code": current_user.role_code,
            "school_code": current_user.school_code,
            "teacher_id_persona": current_user.teacher_id_persona,
            "student_nie": current_user.student_nie,
            "filters": {
                "school_code": school_code,
                "academic_year": academic_year,
                "grade_label": grade_label,
                "section_code": section_code,
                "modality": modality,
                "submodality": submodality,
                "nie": nie,
                "q": q,
            },
        },
    )


def get_enrollment_detail(db: Session, current_user: User, enrollment_id: int) -> StudentEnrollment | None:
    return db.scalar(
        visible_enrollments_stmt(db, current_user)
        .options(*ENROLLMENT_LIST_OPTIONS)
        .where(StudentEnrollment.id == enrollment_id)
    )


def create_enrollment_record(db: Session, payload: StudentEnrollmentCreate) -> StudentEnrollment:
    enrollment = save_enrollment(db, payload)
    invalidate_namespace("enrollments")
    return enrollment
