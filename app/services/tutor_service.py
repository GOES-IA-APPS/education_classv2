from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import StudentTutor, StudentTutorStudentLink, User
from app.repositories.tutors import (
    STUDENT_TUTOR_LIST_OPTIONS,
    create_student_tutor,
    get_student_tutor_by_id,
    link_tutor_to_student,
    list_student_tutors,
)
from app.schemas.tutor import StudentTutorCreate
from app.schemas.user import UserCreate
from app.services.access_service import visible_tutors_stmt
from app.services.user_service import create_user


def search_tutors(
    db: Session,
    current_user: User,
    *,
    student_nie: str | None = None,
    q: str | None = None,
) -> list[StudentTutor]:
    stmt = visible_tutors_stmt(db, current_user).options(*STUDENT_TUTOR_LIST_OPTIONS)
    if student_nie:
        stmt = stmt.where(
            StudentTutor.student_links.any(
                StudentTutorStudentLink.student_nie == student_nie
            )
        )
    if q:
        stmt = stmt.where(StudentTutor.full_name.ilike(f"%{q}%"))
    return list_student_tutors(db, stmt)


def get_tutor_detail(db: Session, current_user: User, tutor_id: int) -> StudentTutor | None:
    return db.scalar(
        visible_tutors_stmt(db, current_user)
        .options(*STUDENT_TUTOR_LIST_OPTIONS)
        .where(StudentTutor.id == tutor_id)
    )


def create_tutor_record(db: Session, payload: StudentTutorCreate, current_user: User) -> StudentTutor:
    tutor = create_student_tutor(
        db,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        dui=payload.dui,
        address=payload.address,
        notes=payload.notes,
    )
    if payload.student_nie:
        link_tutor_to_student(
            db,
            tutor_id=tutor.id,
            student_nie=payload.student_nie,
            relationship_label=payload.relationship_label,
            is_primary=payload.is_primary,
            notes=payload.notes,
        )
    if payload.user_email and payload.user_password:
        create_user(
            db,
            UserCreate(
                email=payload.user_email,
                full_name=payload.user_full_name or payload.full_name,
                password=payload.user_password,
                role_code="student_tutor",
                student_tutor_id=tutor.id,
            ),
            current_user,
            auto_commit=False,
        )
    db.commit()
    db.refresh(tutor)
    return tutor
