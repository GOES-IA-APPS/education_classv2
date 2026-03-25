from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Student, StudentTutor, StudentTutorStudentLink, UserStudentTutorLink

STUDENT_TUTOR_LIST_OPTIONS = (
    joinedload(StudentTutor.student_links).joinedload(StudentTutorStudentLink.student),
    joinedload(StudentTutor.user_links).joinedload(UserStudentTutorLink.user),
)


def student_tutor_list_stmt():
    return select(StudentTutor).options(*STUDENT_TUTOR_LIST_OPTIONS)


def get_student_tutor_by_id(db: Session, tutor_id: int) -> StudentTutor | None:
    return db.scalar(student_tutor_list_stmt().where(StudentTutor.id == tutor_id))


def list_student_tutors(db: Session, stmt, limit: int = 200) -> list[StudentTutor]:
    return list(
        db.scalars(stmt.order_by(StudentTutor.full_name).limit(limit)).unique().all()
    )


def create_student_tutor(
    db: Session,
    *,
    full_name: str,
    email: str | None,
    phone: str | None,
    dui: str | None,
    address: str | None,
    notes: str | None,
) -> StudentTutor:
    tutor = StudentTutor(
        full_name=full_name,
        email=email,
        phone=phone,
        dui=dui,
        address=address,
        notes=notes,
        is_active=True,
    )
    db.add(tutor)
    db.flush()
    return tutor


def link_tutor_to_student(
    db: Session,
    *,
    tutor_id: int,
    student_nie: str,
    relationship_label: str | None,
    is_primary: bool,
    notes: str | None,
) -> StudentTutorStudentLink:
    student = db.scalar(select(Student).where(Student.nie == student_nie))
    if not student:
        raise ValueError("El alumno indicado no existe.")
    link = db.scalar(
        select(StudentTutorStudentLink).where(
            StudentTutorStudentLink.student_tutor_id == tutor_id,
            StudentTutorStudentLink.student_nie == student_nie,
        )
    )
    if not link:
        link = StudentTutorStudentLink(
            student_tutor_id=tutor_id,
            student_nie=student_nie,
        )
        db.add(link)
    link.relationship_label = relationship_label
    link.is_primary = is_primary
    link.notes = notes
    db.flush()
    return link


def link_user_to_tutor(
    db: Session,
    *,
    user_id: int,
    tutor_id: int,
) -> UserStudentTutorLink:
    link = db.scalar(
        select(UserStudentTutorLink).where(
            UserStudentTutorLink.user_id == user_id,
            UserStudentTutorLink.student_tutor_id == tutor_id,
        )
    )
    if not link:
        link = UserStudentTutorLink(user_id=user_id, student_tutor_id=tutor_id)
        db.add(link)
        db.flush()
    return link
