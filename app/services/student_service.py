from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Student, StudentEnrollment, User
from app.repositories.students import (
    STUDENT_LIST_OPTIONS,
    list_students,
    save_student,
)
from app.schemas.academic import StudentCreate
from app.services.pagination_service import paginate_entities
from app.services.access_service import visible_students_stmt
from app.utils.cache import invalidate_namespace
from app.utils.pagination import DEFAULT_PER_PAGE, PaginationResult


def search_students(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    nie: str | None = None,
) -> list[Student]:
    stmt = visible_students_stmt(db, current_user).options(*STUDENT_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(Student.student_enrollments.any(StudentEnrollment.school_code == school_code))
    if academic_year:
        stmt = stmt.where(Student.student_enrollments.any(StudentEnrollment.academic_year == academic_year))
    if grade_label:
        stmt = stmt.where(Student.student_enrollments.any(StudentEnrollment.grade_label == grade_label))
    if section_code:
        stmt = stmt.where(Student.student_enrollments.any(StudentEnrollment.section_code == section_code))
    if nie:
        stmt = stmt.where(Student.nie == nie)
    return list_students(db, stmt)


def search_students_page(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    nie: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> PaginationResult[Student]:
    base_stmt = visible_students_stmt(db, current_user)
    if school_code:
        base_stmt = base_stmt.where(Student.student_enrollments.any(StudentEnrollment.school_code == school_code))
    if academic_year:
        base_stmt = base_stmt.where(Student.student_enrollments.any(StudentEnrollment.academic_year == academic_year))
    if grade_label:
        base_stmt = base_stmt.where(Student.student_enrollments.any(StudentEnrollment.grade_label == grade_label))
    if section_code:
        base_stmt = base_stmt.where(Student.student_enrollments.any(StudentEnrollment.section_code == section_code))
    if nie:
        base_stmt = base_stmt.where(Student.nie == nie)
    fetch_stmt = base_stmt.options(*STUDENT_LIST_OPTIONS)
    return paginate_entities(
        db,
        base_stmt=base_stmt,
        fetch_stmt=fetch_stmt,
        id_column=Student.nie,
        order_by=(Student.last_name1, Student.last_name2, Student.first_name1, Student.nie),
        page=page,
        per_page=per_page,
        cache_namespace="students",
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
                "nie": nie,
            },
        },
    )


def get_student_detail(db: Session, current_user: User, nie: str) -> Student | None:
    return db.scalar(
        visible_students_stmt(db, current_user)
        .options(*STUDENT_LIST_OPTIONS)
        .where(Student.nie == nie)
    )


def create_student_record(db: Session, payload: StudentCreate) -> Student:
    student = save_student(db, payload)
    invalidate_namespace("students")
    return student
