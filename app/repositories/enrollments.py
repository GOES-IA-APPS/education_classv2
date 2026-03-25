from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import School, Student, StudentEnrollment
from app.schemas.academic import StudentEnrollmentCreate

ENROLLMENT_LIST_OPTIONS = (
    joinedload(StudentEnrollment.student),
    joinedload(StudentEnrollment.school),
)


def enrollment_list_stmt():
    return select(StudentEnrollment).options(*ENROLLMENT_LIST_OPTIONS)


def get_enrollment_by_id(db: Session, enrollment_id: int) -> StudentEnrollment | None:
    return db.scalar(enrollment_list_stmt().where(StudentEnrollment.id == enrollment_id))


def list_enrollments(db: Session, stmt, limit: int = 200) -> list[StudentEnrollment]:
    return list(
        db.scalars(
            stmt.order_by(
                StudentEnrollment.academic_year.desc(),
                StudentEnrollment.school_code,
                StudentEnrollment.grade_label,
                StudentEnrollment.section_code,
            ).limit(limit)
        ).unique().all()
    )


def save_enrollment(db: Session, payload: StudentEnrollmentCreate) -> StudentEnrollment:
    student = db.scalar(select(Student).where(Student.nie == payload.nie))
    if not student:
        raise ValueError("El alumno indicado no existe.")

    school = db.get(School, payload.school_code)
    if not school:
        raise ValueError("La escuela indicada no existe.")

    enrollment = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.nie == payload.nie,
            StudentEnrollment.school_code == payload.school_code,
            StudentEnrollment.academic_year == payload.academic_year,
        )
    )
    if not enrollment:
        enrollment = StudentEnrollment(
            nie=payload.nie,
            school_code=payload.school_code,
            academic_year=payload.academic_year,
        )
        if db.bind and db.bind.dialect.name == "sqlite":
            enrollment.id = (db.scalar(select(func.coalesce(func.max(StudentEnrollment.id), 0) + 1)) or 1)
        db.add(enrollment)
    enrollment.section_code = payload.section_code
    enrollment.grade_label = payload.grade_label
    enrollment.modality = payload.modality
    enrollment.submodality = payload.submodality
    db.commit()
    db.refresh(enrollment)
    return enrollment
