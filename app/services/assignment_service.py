from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import TeacherAssignment, User
from app.repositories.assignments import (
    ASSIGNMENT_LIST_OPTIONS,
    get_assignment_by_id,
    list_assignments,
    save_assignment,
)
from app.schemas.academic import TeacherAssignmentCreate
from app.services.pagination_service import paginate_entities
from app.services.access_service import visible_assignments_stmt, visible_director_assignments_stmt
from app.utils.cache import invalidate_namespace
from app.utils.pagination import DEFAULT_PER_PAGE, PaginationResult


def search_assignments(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_name: str | None = None,
    id_persona: str | None = None,
    component_type: str | None = None,
) -> list[TeacherAssignment]:
    stmt = visible_assignments_stmt(db, current_user).options(*ASSIGNMENT_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(TeacherAssignment.school_code == school_code)
    if academic_year:
        stmt = stmt.where(TeacherAssignment.academic_year == academic_year)
    if grade_label:
        stmt = stmt.where(TeacherAssignment.grade_label == grade_label)
    if section_name:
        stmt = stmt.where(
            (TeacherAssignment.section_name == section_name)
            | (TeacherAssignment.section_id == section_name)
        )
    if id_persona:
        stmt = stmt.where(TeacherAssignment.id_persona == id_persona)
    if component_type:
        stmt = stmt.where(TeacherAssignment.component_type == component_type)
    return list_assignments(db, stmt)


def search_assignments_page(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_name: str | None = None,
    id_persona: str | None = None,
    component_type: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> PaginationResult[TeacherAssignment]:
    base_stmt = visible_assignments_stmt(db, current_user)
    if school_code:
        base_stmt = base_stmt.where(TeacherAssignment.school_code == school_code)
    if academic_year:
        base_stmt = base_stmt.where(TeacherAssignment.academic_year == academic_year)
    if grade_label:
        base_stmt = base_stmt.where(TeacherAssignment.grade_label == grade_label)
    if section_name:
        base_stmt = base_stmt.where(
            (TeacherAssignment.section_name == section_name)
            | (TeacherAssignment.section_id == section_name)
        )
    if id_persona:
        base_stmt = base_stmt.where(TeacherAssignment.id_persona == id_persona)
    if component_type:
        base_stmt = base_stmt.where(TeacherAssignment.component_type == component_type)
    fetch_stmt = base_stmt.options(*ASSIGNMENT_LIST_OPTIONS)
    return paginate_entities(
        db,
        base_stmt=base_stmt,
        fetch_stmt=fetch_stmt,
        id_column=TeacherAssignment.id,
        order_by=(
            TeacherAssignment.academic_year.desc(),
            TeacherAssignment.school_code,
            TeacherAssignment.component_type,
            TeacherAssignment.grade_label,
            TeacherAssignment.section_id,
            TeacherAssignment.id.desc(),
        ),
        page=page,
        per_page=per_page,
        cache_namespace="assignments",
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
                "section_name": section_name,
                "id_persona": id_persona,
                "component_type": component_type,
            },
        },
    )


def get_assignment_detail(db: Session, current_user: User, assignment_id: int) -> TeacherAssignment | None:
    return db.scalar(
        visible_assignments_stmt(db, current_user)
        .options(*ASSIGNMENT_LIST_OPTIONS)
        .where(TeacherAssignment.id == assignment_id)
    )


def list_director_assignments(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
) -> list[TeacherAssignment]:
    stmt = visible_director_assignments_stmt(db, current_user).options(*ASSIGNMENT_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(TeacherAssignment.school_code == school_code)
    if academic_year:
        stmt = stmt.where(TeacherAssignment.academic_year == academic_year)
    return list_assignments(db, stmt)


def list_director_assignments_page(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> PaginationResult[TeacherAssignment]:
    base_stmt = visible_director_assignments_stmt(db, current_user)
    if school_code:
        base_stmt = base_stmt.where(TeacherAssignment.school_code == school_code)
    if academic_year:
        base_stmt = base_stmt.where(TeacherAssignment.academic_year == academic_year)
    fetch_stmt = base_stmt.options(*ASSIGNMENT_LIST_OPTIONS)
    return paginate_entities(
        db,
        base_stmt=base_stmt,
        fetch_stmt=fetch_stmt,
        id_column=TeacherAssignment.id,
        order_by=(
            TeacherAssignment.academic_year.desc(),
            TeacherAssignment.school_code,
            TeacherAssignment.id.desc(),
        ),
        page=page,
        per_page=per_page,
        cache_namespace="directors",
        cache_scope={
            "user_id": current_user.id,
            "role_code": current_user.role_code,
            "school_code": current_user.school_code,
            "teacher_id_persona": current_user.teacher_id_persona,
            "student_nie": current_user.student_nie,
            "filters": {
                "school_code": school_code,
                "academic_year": academic_year,
            },
        },
    )


def create_assignment_record(db: Session, payload: TeacherAssignmentCreate) -> TeacherAssignment:
    assignment = save_assignment(db, payload)
    invalidate_namespace("assignments")
    invalidate_namespace("directors")
    return assignment
