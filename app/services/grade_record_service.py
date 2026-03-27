from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import GradeRecord, StudentEnrollment, SubjectCatalog, TeacherAssignment, User
from app.repositories.grade_records import (
    GRADE_RECORD_LIST_OPTIONS,
    create_grade_record,
    get_grade_record_by_id,
    list_grade_records,
    update_grade_record,
)
from app.schemas.phase3 import GradeRecordCreate, GradeRecordUpdate
from app.services.pagination_service import paginate_entities
from app.services.access_service import visible_assignments_stmt, visible_grade_records_stmt
from app.utils.pagination import DEFAULT_PER_PAGE, PaginationResult


def _validate_note_values(score: float | None, weight: float | None) -> None:
    if score is not None and (score < 0 or score > 100):
        raise ValueError("La nota debe estar entre 0 y 100.")
    if weight is not None and (weight <= 0 or weight > 100):
        raise ValueError("El peso debe ser mayor que 0 y menor o igual a 100.")


def _section_matches(assignment: TeacherAssignment, section_value: str | None) -> bool:
    if not section_value:
        return True
    return section_value in {assignment.section_id, assignment.section_name}


def _grade_matches(assignment: TeacherAssignment, grade_label: str | None) -> bool:
    if not grade_label or not assignment.grade_label:
        return True
    return assignment.grade_label == grade_label


def _grade_record_search_clause(q: str):
    query = f"%{q.strip().lower()}%"
    return or_(
        func.lower(func.coalesce(GradeRecord.student_nie, "")).like(query),
        func.lower(func.coalesce(GradeRecord.teacher_id_persona, "")).like(query),
        func.lower(func.coalesce(GradeRecord.subject_name, "")).like(query),
        func.lower(func.coalesce(GradeRecord.subject_code, "")).like(query),
        func.lower(func.coalesce(GradeRecord.evaluation_type, "")).like(query),
        func.lower(func.coalesce(GradeRecord.evaluation_name, "")).like(query),
        func.lower(func.coalesce(GradeRecord.grade_label, "")).like(query),
        func.lower(func.coalesce(GradeRecord.section_code, "")).like(query),
        func.lower(func.coalesce(GradeRecord.section_id, "")).like(query),
    )


def _resolve_subject_snapshot(db: Session, payload: GradeRecordCreate | GradeRecordUpdate) -> tuple[int | None, str | None, str | None]:
    if not payload.subject_catalog_id:
        return payload.subject_catalog_id, payload.subject_code, getattr(payload, "subject_name", None)
    subject_catalog = db.get(SubjectCatalog, payload.subject_catalog_id)
    if not subject_catalog:
        raise ValueError("La materia indicada no existe.")
    subject_code = payload.subject_code or subject_catalog.subject_code
    subject_name = getattr(payload, "subject_name", None) or subject_catalog.subject_name
    return subject_catalog.id, subject_code, subject_name


def _resolve_enrollment(
    db: Session,
    *,
    student_nie: str,
    school_code: str,
    academic_year: int,
) -> StudentEnrollment | None:
    return db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.nie == student_nie,
            StudentEnrollment.school_code == school_code,
            StudentEnrollment.academic_year == academic_year,
        )
    )


def _resolve_teacher_assignment_for_teacher(
    db: Session,
    current_user: User,
    payload: GradeRecordCreate,
) -> TeacherAssignment:
    stmt = visible_assignments_stmt(db, current_user).where(
        TeacherAssignment.school_code == payload.school_code,
        TeacherAssignment.academic_year == payload.academic_year,
    )
    section_value = payload.section_id or payload.section_code
    assignments = db.scalars(stmt.order_by(TeacherAssignment.id.desc())).all()
    for assignment in assignments:
        if _grade_matches(assignment, payload.grade_label) and _section_matches(assignment, section_value):
            return assignment
    raise ValueError("El docente no tiene una asignación real compatible para registrar esta nota.")


def search_grade_records(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    student_nie: str | None = None,
    teacher_id_persona: str | None = None,
    subject_name: str | None = None,
) -> list[GradeRecord]:
    stmt = visible_grade_records_stmt(db, current_user).options(*GRADE_RECORD_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(GradeRecord.school_code == school_code)
    if academic_year:
        stmt = stmt.where(GradeRecord.academic_year == academic_year)
    if grade_label:
        stmt = stmt.where(GradeRecord.grade_label == grade_label)
    if section_code:
        stmt = stmt.where(
            (GradeRecord.section_code == section_code) | (GradeRecord.section_id == section_code)
        )
    if student_nie:
        stmt = stmt.where(GradeRecord.student_nie == student_nie)
    if teacher_id_persona:
        stmt = stmt.where(GradeRecord.teacher_id_persona == teacher_id_persona)
    if subject_name:
        stmt = stmt.where(GradeRecord.subject_name.ilike(f"%{subject_name}%"))
    return list_grade_records(db, stmt)


def search_grade_records_page(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> PaginationResult[GradeRecord]:
    base_stmt = visible_grade_records_stmt(db, current_user)
    if school_code:
        base_stmt = base_stmt.where(GradeRecord.school_code == school_code)
    if q:
        base_stmt = base_stmt.where(_grade_record_search_clause(q))
    fetch_stmt = base_stmt.options(*GRADE_RECORD_LIST_OPTIONS)
    return paginate_entities(
        db,
        base_stmt=base_stmt,
        fetch_stmt=fetch_stmt,
        id_column=GradeRecord.id,
        order_by=(
            GradeRecord.academic_year.desc(),
            GradeRecord.school_code,
            GradeRecord.grade_label,
            GradeRecord.section_code,
            GradeRecord.subject_name,
            GradeRecord.student_nie,
            GradeRecord.id,
        ),
        page=page,
        per_page=per_page,
        cache_namespace="grades",
        cache_scope={
            "user_id": current_user.id,
            "role_code": current_user.role_code,
            "school_code": current_user.school_code,
            "teacher_id_persona": current_user.teacher_id_persona,
            "student_nie": current_user.student_nie,
            "filters": {
                "school_code": school_code,
                "q": q,
            },
        },
    )


def get_grade_record_detail(db: Session, current_user: User, grade_record_id: int) -> GradeRecord | None:
    return db.scalar(
        visible_grade_records_stmt(db, current_user)
        .options(*GRADE_RECORD_LIST_OPTIONS)
        .where(GradeRecord.id == grade_record_id)
    )


def create_grade_record_entry(db: Session, payload: GradeRecordCreate, current_user: User) -> GradeRecord:
    _validate_note_values(payload.score, payload.weight)
    enrollment = _resolve_enrollment(
        db,
        student_nie=payload.student_nie,
        school_code=payload.school_code,
        academic_year=payload.academic_year,
    )
    if not enrollment:
        raise ValueError("No existe una matrícula real compatible para ese alumno, escuela y año.")

    subject_catalog_id, subject_code, subject_name = _resolve_subject_snapshot(db, payload)
    if not subject_name:
        raise ValueError("Debe indicar la materia de la nota.")

    update_data = {
        "subject_catalog_id": subject_catalog_id,
        "subject_code": subject_code,
        "subject_name": subject_name,
        "grade_label": payload.grade_label or enrollment.grade_label,
        "section_code": payload.section_code or enrollment.section_code,
        "created_by_user_id": current_user.id,
        "updated_by_user_id": current_user.id,
    }

    if current_user.role_code == "teacher":
        assignment = None
        if payload.teacher_assignment_id:
            assignment = db.scalar(
                visible_assignments_stmt(db, current_user).where(
                    TeacherAssignment.id == payload.teacher_assignment_id
                )
            )
            if not assignment:
                raise ValueError("La asignación indicada no pertenece al docente autenticado.")
        else:
            assignment = _resolve_teacher_assignment_for_teacher(
                db,
                current_user,
                payload.model_copy(update=update_data),
            )
        if assignment.school_code != enrollment.school_code or assignment.academic_year != enrollment.academic_year:
            raise ValueError("La asignación docente no coincide con la matrícula del alumno.")
        if assignment.grade_label and enrollment.grade_label and assignment.grade_label != enrollment.grade_label:
            raise ValueError("La asignación docente no coincide con el grado matriculado del alumno.")
        if assignment.section_id and enrollment.section_code and enrollment.section_code not in {
            assignment.section_id,
            assignment.section_name,
        }:
            raise ValueError("La asignación docente no coincide con la sección matriculada del alumno.")
        update_data.update(
            {
                "teacher_id_persona": current_user.teacher_id_persona,
                "teacher_assignment_id": assignment.id,
                "school_code": assignment.school_code,
                "academic_year": assignment.academic_year,
                "grade_label": assignment.grade_label or update_data["grade_label"],
                "section_id": assignment.section_id,
                "section_code": enrollment.section_code or assignment.section_id or assignment.section_name,
            }
        )
    elif payload.teacher_assignment_id:
        assignment = db.get(TeacherAssignment, payload.teacher_assignment_id)
        if not assignment:
            raise ValueError("La asignación docente indicada no existe.")
        update_data.update(
            {
                "teacher_id_persona": payload.teacher_id_persona or assignment.id_persona,
                "grade_label": payload.grade_label or assignment.grade_label or update_data["grade_label"],
                "section_id": payload.section_id or assignment.section_id,
            }
        )

    prepared = payload.model_copy(update=update_data)
    return create_grade_record(db, prepared)


def update_grade_record_entry(
    db: Session,
    grade_record_id: int,
    payload: GradeRecordUpdate,
    current_user: User,
) -> GradeRecord:
    record = get_grade_record_detail(db, current_user, grade_record_id)
    if not record:
        raise ValueError("La nota indicada no es visible para el usuario actual.")

    score = payload.score if payload.score is not None else float(record.score) if record.score is not None else None
    weight = payload.weight if payload.weight is not None else float(record.weight) if record.weight is not None else None
    _validate_note_values(score, weight)

    subject_catalog_id, subject_code, subject_name = _resolve_subject_snapshot(db, payload)
    prepared = payload.model_copy(
        update={
            "subject_catalog_id": subject_catalog_id,
            "subject_code": subject_code,
            "subject_name": subject_name or record.subject_name,
        }
    )
    return update_grade_record(db, record, prepared, updated_by_user_id=current_user.id)
