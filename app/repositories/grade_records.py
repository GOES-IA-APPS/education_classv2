from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import GradeRecord, School, Student, SubjectCatalog, Teacher, TeacherAssignment

GRADE_RECORD_LIST_OPTIONS = (
    joinedload(GradeRecord.school),
    joinedload(GradeRecord.student),
    joinedload(GradeRecord.teacher),
    joinedload(GradeRecord.teacher_assignment).joinedload(TeacherAssignment.school),
    joinedload(GradeRecord.subject_catalog),
)


def grade_record_list_stmt():
    return select(GradeRecord).options(*GRADE_RECORD_LIST_OPTIONS)


def get_grade_record_by_id(db: Session, grade_record_id: int) -> GradeRecord | None:
    return db.scalar(grade_record_list_stmt().where(GradeRecord.id == grade_record_id))


def list_grade_records(db: Session, stmt, limit: int = 300) -> list[GradeRecord]:
    return list(
        db.scalars(
            stmt.order_by(
                GradeRecord.academic_year.desc(),
                GradeRecord.school_code,
                GradeRecord.grade_label,
                GradeRecord.section_code,
                GradeRecord.subject_name,
                GradeRecord.student_nie,
            ).limit(limit)
        ).unique().all()
    )


def create_grade_record(db: Session, payload) -> GradeRecord:
    school = db.get(School, payload.school_code)
    if not school:
        raise ValueError("La escuela indicada no existe.")

    student = db.scalar(select(Student).where(Student.nie == payload.student_nie))
    if not student:
        raise ValueError("El alumno indicado no existe.")

    if payload.teacher_id_persona:
        if not db.scalar(select(Teacher).where(Teacher.id_persona == payload.teacher_id_persona)):
            raise ValueError("El docente indicado no existe.")

    if payload.teacher_assignment_id:
        if not db.get(TeacherAssignment, payload.teacher_assignment_id):
            raise ValueError("La asignación docente indicada no existe.")

    if payload.subject_catalog_id:
        if not db.get(SubjectCatalog, payload.subject_catalog_id):
            raise ValueError("La materia indicada no existe.")

    record = GradeRecord(
        school_code=payload.school_code,
        student_nie=payload.student_nie,
        teacher_id_persona=payload.teacher_id_persona,
        teacher_assignment_id=payload.teacher_assignment_id,
        subject_catalog_id=payload.subject_catalog_id,
        academic_year=payload.academic_year,
        grade_label=payload.grade_label,
        section_code=payload.section_code,
        section_id=payload.section_id,
        subject_code=payload.subject_code,
        subject_name=payload.subject_name,
        evaluation_type=payload.evaluation_type,
        evaluation_name=payload.evaluation_name,
        weight=payload.weight,
        score=payload.score,
        observations=payload.observations,
        created_by_user_id=payload.created_by_user_id,
        updated_by_user_id=payload.updated_by_user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_grade_record(db: Session, record: GradeRecord, payload, *, updated_by_user_id: int | None = None) -> GradeRecord:
    record.subject_catalog_id = payload.subject_catalog_id
    record.subject_code = payload.subject_code
    record.subject_name = payload.subject_name or record.subject_name
    record.evaluation_type = payload.evaluation_type
    record.evaluation_name = payload.evaluation_name
    record.weight = payload.weight
    record.score = payload.score
    record.observations = payload.observations
    record.updated_by_user_id = updated_by_user_id
    db.commit()
    db.refresh(record)
    return record
