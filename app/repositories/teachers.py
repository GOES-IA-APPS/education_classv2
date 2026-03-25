from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Teacher, TeacherAssignment
from app.schemas.academic import TeacherCreate

TEACHER_LIST_OPTIONS = (
    joinedload(Teacher.assignments).joinedload(TeacherAssignment.school),
)


def teacher_list_stmt():
    return select(Teacher).options(*TEACHER_LIST_OPTIONS)


def get_teacher_by_id_persona(db: Session, id_persona: str) -> Teacher | None:
    return db.scalar(teacher_list_stmt().where(Teacher.id_persona == id_persona))


def list_teachers(db: Session, stmt, limit: int = 200) -> list[Teacher]:
    return list(
        db.scalars(
            stmt.order_by(Teacher.last_names, Teacher.first_names).limit(limit)
        ).unique().all()
    )


def save_teacher(db: Session, payload: TeacherCreate) -> Teacher:
    teacher = db.scalar(select(Teacher).where(Teacher.id_persona == payload.id_persona))
    if not teacher:
        teacher = Teacher(id_persona=payload.id_persona)
        if db.bind and db.bind.dialect.name == "sqlite":
            teacher.id = (db.scalar(select(func.coalesce(func.max(Teacher.id), 0) + 1)) or 1)
        db.add(teacher)
    teacher.nip = payload.nip
    teacher.dui = payload.dui
    teacher.first_names = payload.first_names
    teacher.last_names = payload.last_names
    teacher.gender = payload.gender
    teacher.specialty = payload.specialty
    db.commit()
    db.refresh(teacher)
    return teacher
