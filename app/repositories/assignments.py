from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import School, Teacher, TeacherAssignment
from app.schemas.academic import TeacherAssignmentCreate

ASSIGNMENT_LIST_OPTIONS = (
    joinedload(TeacherAssignment.teacher),
    joinedload(TeacherAssignment.school),
)


def assignment_list_stmt():
    return select(TeacherAssignment).options(*ASSIGNMENT_LIST_OPTIONS)


def get_assignment_by_id(db: Session, assignment_id: int) -> TeacherAssignment | None:
    return db.scalar(assignment_list_stmt().where(TeacherAssignment.id == assignment_id))


def list_assignments(db: Session, stmt, limit: int = 200) -> list[TeacherAssignment]:
    return list(
        db.scalars(
            stmt.order_by(
                TeacherAssignment.academic_year.desc(),
                TeacherAssignment.school_code,
                TeacherAssignment.component_type,
                TeacherAssignment.grade_label,
                TeacherAssignment.section_id,
            ).limit(limit)
        ).unique().all()
    )


def save_assignment(db: Session, payload: TeacherAssignmentCreate) -> TeacherAssignment:
    teacher = db.scalar(select(Teacher).where(Teacher.id_persona == payload.id_persona))
    if not teacher:
        raise ValueError("El docente indicado no existe.")

    school = db.get(School, payload.school_code)
    if not school:
        raise ValueError("La escuela indicada no existe.")

    assignment = db.scalar(
        select(TeacherAssignment).where(
            TeacherAssignment.id_persona == payload.id_persona,
            TeacherAssignment.school_code == payload.school_code,
            TeacherAssignment.academic_year == payload.academic_year,
            TeacherAssignment.section_id == payload.section_id,
        )
    )
    if not assignment:
        assignment = TeacherAssignment(
            id_persona=payload.id_persona,
            school_code=payload.school_code,
            academic_year=payload.academic_year,
            section_id=payload.section_id,
        )
        if db.bind and db.bind.dialect.name == "sqlite":
            assignment.id = (db.scalar(select(func.coalesce(func.max(TeacherAssignment.id), 0) + 1)) or 1)
        db.add(assignment)
    assignment.component_type = payload.component_type
    assignment.grade_label = payload.grade_label
    assignment.section_name = payload.section_name
    assignment.shift = payload.shift
    assignment.cod_adscrito = payload.cod_adscrito
    db.commit()
    db.refresh(assignment)
    return assignment
