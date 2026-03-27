from __future__ import annotations

from sqlalchemy import delete, func, inspect, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Student, StudentEnrollment, User
from app.repositories.students import (
    list_students,
    save_student,
    student_list_options,
    student_tutor_tables_available,
)
from app.schemas.academic import StudentCreate
from app.services.pagination_service import paginate_entities
from app.services.access_service import visible_students_stmt
from app.utils.cache import invalidate_namespace
from app.utils.pagination import DEFAULT_PER_PAGE, PaginationResult


def _attach_student_view_metadata(db: Session, students: list[Student]) -> list[Student]:
    tutors_available = student_tutor_tables_available(db)
    for student in students:
        visible_tutor_links = list(student.student_tutor_links) if tutors_available else []
        setattr(
            student,
            "visible_tutor_count",
            len(visible_tutor_links),
        )
        setattr(student, "visible_tutor_links", visible_tutor_links)
        setattr(student, "tutors_available", tutors_available)
    return students


def _student_search_clause(q: str):
    query = f"%{q.strip().lower()}%"
    return or_(
        func.lower(func.coalesce(Student.nie, "")).like(query),
        func.lower(func.coalesce(Student.first_name1, "")).like(query),
        func.lower(func.coalesce(Student.first_name2, "")).like(query),
        func.lower(func.coalesce(Student.first_name3, "")).like(query),
        func.lower(func.coalesce(Student.last_name1, "")).like(query),
        func.lower(func.coalesce(Student.last_name2, "")).like(query),
        func.lower(func.coalesce(Student.last_name3, "")).like(query),
        func.lower(func.coalesce(Student.father_full_name, "")).like(query),
        func.lower(func.coalesce(Student.mother_full_name, "")).like(query),
    )


def search_students(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    nie: str | None = None,
    q: str | None = None,
) -> list[Student]:
    stmt = visible_students_stmt(db, current_user).options(*student_list_options(db))
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
    if q:
        stmt = stmt.where(_student_search_clause(q))
    return _attach_student_view_metadata(db, list_students(db, stmt))


def search_students_page(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    nie: str | None = None,
    q: str | None = None,
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
    if q:
        base_stmt = base_stmt.where(_student_search_clause(q))
    fetch_stmt = base_stmt.options(*student_list_options(db))
    pagination = paginate_entities(
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
                "q": q,
            },
        },
    )
    pagination.items = _attach_student_view_metadata(db, pagination.items)
    return pagination


def get_student_detail(db: Session, current_user: User, nie: str) -> Student | None:
    student = db.scalar(
        visible_students_stmt(db, current_user)
        .options(*student_list_options(db))
        .where(Student.nie == nie)
    )
    if student:
        _attach_student_view_metadata(db, [student])
    return student


def create_student_record(db: Session, payload: StudentCreate) -> Student:
    student = save_student(db, payload)
    invalidate_namespace("students")
    return student


def update_student_record(db: Session, nie: str, payload: StudentCreate) -> Student:
    student = db.scalar(select(Student).where(Student.nie == nie))
    if not student:
        raise ValueError("Alumno no encontrado.")
    updated = save_student(db, payload)
    invalidate_namespace("students")
    return updated


def _count_dependency(db: Session, table_name: str, *, column_name: str, value) -> int:
    return int(
        db.execute(
            text(f"SELECT COUNT(*) AS total FROM {table_name} WHERE {column_name} = :value"),
            {"value": value},
        ).scalar()
        or 0
    )


def delete_student_record(db: Session, current_user: User, nie: str) -> None:
    student = get_student_detail(db, current_user, nie)
    if not student:
        raise ValueError("Alumno no encontrado.")

    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())
    blockers: list[str] = []

    if "student_enrollments" in tables:
        total = _count_dependency(db, "student_enrollments", column_name="nie", value=student.nie)
        if total:
            blockers.append(f"{total} matrícula(s)")

    if "student_tutor_student_links" in tables:
        total = _count_dependency(db, "student_tutor_student_links", column_name="student_nie", value=student.nie)
        if total:
            blockers.append(f"{total} vínculo(s) con tutores")

    if "grade_records" in tables:
        columns = {column["name"] for column in inspector.get_columns("grade_records")}
        if "student_nie" in columns:
            total = _count_dependency(db, "grade_records", column_name="student_nie", value=student.nie)
            if total:
                blockers.append(f"{total} nota(s)")
        elif "student_id" in columns:
            total = _count_dependency(db, "grade_records", column_name="student_id", value=student.id)
            if total:
                blockers.append(f"{total} nota(s)")

    if "report_cards" in tables:
        columns = {column["name"] for column in inspector.get_columns("report_cards")}
        if "student_nie" in columns:
            total = _count_dependency(db, "report_cards", column_name="student_nie", value=student.nie)
            if total:
                blockers.append(f"{total} boleta(s)")
        elif "student_id" in columns:
            total = _count_dependency(db, "report_cards", column_name="student_id", value=student.id)
            if total:
                blockers.append(f"{total} boleta(s)")

    if "users" in tables:
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "student_nie" in columns:
            total = _count_dependency(db, "users", column_name="student_nie", value=student.nie)
            if total:
                blockers.append(f"{total} usuario(s) vinculados")
        elif "student_id" in columns:
            total = _count_dependency(db, "users", column_name="student_id", value=student.id)
            if total:
                blockers.append(f"{total} usuario(s) vinculados")

    if blockers:
        raise ValueError(
            "No se puede eliminar el alumno porque tiene relaciones activas: "
            + ", ".join(blockers)
            + "."
        )

    try:
        db.execute(delete(Student).where(Student.nie == student.nie))
        db.commit()
        invalidate_namespace("students")
    except SQLAlchemyError as exc:
        db.rollback()
        raise ValueError(
            "No se pudo eliminar el alumno por integridad referencial o dependencias activas."
        ) from exc
