from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Student, StudentEnrollment, StudentTutorStudentLink
from app.schemas.academic import StudentCreate

STUDENT_LIST_OPTIONS = (
    joinedload(Student.student_enrollments).joinedload(StudentEnrollment.school),
    joinedload(Student.student_tutor_links).joinedload(StudentTutorStudentLink.student_tutor),
)


def student_list_stmt():
    return select(Student).options(*STUDENT_LIST_OPTIONS)


def get_student_by_nie(db: Session, nie: str) -> Student | None:
    return db.scalar(student_list_stmt().where(Student.nie == nie))


def list_students(db: Session, stmt, limit: int = 200) -> list[Student]:
    return list(
        db.scalars(
            stmt.order_by(Student.last_name1, Student.last_name2, Student.first_name1).limit(limit)
        ).unique().all()
    )


def save_student(db: Session, payload: StudentCreate) -> Student:
    student = db.scalar(select(Student).where(Student.nie == payload.nie))
    if not student:
        student = Student(nie=payload.nie)
        if db.bind and db.bind.dialect.name == "sqlite":
            student.id = (db.scalar(select(func.coalesce(func.max(Student.id), 0) + 1)) or 1)
        db.add(student)
    student.gender = payload.gender
    student.first_name1 = payload.first_name1
    student.first_name2 = payload.first_name2
    student.first_name3 = payload.first_name3
    student.last_name1 = payload.last_name1
    student.last_name2 = payload.last_name2
    student.last_name3 = payload.last_name3
    student.birth_date = payload.birth_date
    student.age_current = payload.age_current
    student.father_full_name = payload.father_full_name
    student.mother_full_name = payload.mother_full_name
    student.address_full = payload.address_full
    db.commit()
    db.refresh(student)
    return student
