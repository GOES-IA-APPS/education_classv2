from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Teacher, TeacherAssignment, User
from app.repositories.teachers import (
    TEACHER_LIST_OPTIONS,
    get_teacher_by_id_persona,
    list_teachers,
    save_teacher,
)
from app.schemas.academic import TeacherCreate
from app.services.pagination_service import paginate_entities
from app.services.access_service import visible_teachers_stmt
from app.utils.cache import invalidate_namespace
from app.utils.pagination import DEFAULT_PER_PAGE, PaginationResult


def _teacher_search_clause(q: str):
    query = f"%{q.strip().lower()}%"
    return or_(
        func.lower(func.coalesce(Teacher.id_persona, "")).like(query),
        func.lower(func.coalesce(Teacher.nip, "")).like(query),
        func.lower(func.coalesce(Teacher.dui, "")).like(query),
        func.lower(func.coalesce(Teacher.first_names, "")).like(query),
        func.lower(func.coalesce(Teacher.last_names, "")).like(query),
        func.lower(func.coalesce(Teacher.specialty, "")).like(query),
    )


def search_teachers(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    id_persona: str | None = None,
    gender: str | None = None,
    q: str | None = None,
) -> list[Teacher]:
    stmt = visible_teachers_stmt(db, current_user).options(*TEACHER_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(Teacher.assignments.any(TeacherAssignment.school_code == school_code))
    if id_persona:
        stmt = stmt.where(Teacher.id_persona == id_persona)
    if gender:
        stmt = stmt.where(Teacher.gender == gender)
    if q:
        stmt = stmt.where(_teacher_search_clause(q))
    return list_teachers(db, stmt)


def search_teachers_page(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    id_persona: str | None = None,
    gender: str | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> PaginationResult[Teacher]:
    base_stmt = visible_teachers_stmt(db, current_user)
    if school_code:
        base_stmt = base_stmt.where(Teacher.assignments.any(TeacherAssignment.school_code == school_code))
    if id_persona:
        base_stmt = base_stmt.where(Teacher.id_persona == id_persona)
    if gender:
        base_stmt = base_stmt.where(Teacher.gender == gender)
    if q:
        base_stmt = base_stmt.where(_teacher_search_clause(q))
    fetch_stmt = base_stmt.options(*TEACHER_LIST_OPTIONS)
    return paginate_entities(
        db,
        base_stmt=base_stmt,
        fetch_stmt=fetch_stmt,
        id_column=Teacher.id_persona,
        order_by=(Teacher.last_names, Teacher.first_names, Teacher.id_persona),
        page=page,
        per_page=per_page,
        cache_namespace="teachers",
        cache_scope={
            "user_id": current_user.id,
            "role_code": current_user.role_code,
            "school_code": current_user.school_code,
            "teacher_id_persona": current_user.teacher_id_persona,
            "student_nie": current_user.student_nie,
            "filters": {
                "school_code": school_code,
                "id_persona": id_persona,
                "gender": gender,
                "q": q,
            },
        },
    )


def get_teacher_detail(db: Session, current_user: User, id_persona: str) -> Teacher | None:
    return db.scalar(
        visible_teachers_stmt(db, current_user)
        .options(*TEACHER_LIST_OPTIONS)
        .where(Teacher.id_persona == id_persona)
    )


def create_teacher_record(db: Session, payload: TeacherCreate) -> Teacher:
    teacher = save_teacher(db, payload)
    invalidate_namespace("teachers")
    return teacher
