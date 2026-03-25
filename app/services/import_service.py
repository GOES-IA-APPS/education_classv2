from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import School, Student, StudentEnrollment, Teacher, TeacherAssignment
from app.utils.importing import (
    CSV_SPECS,
    CsvHeaderError,
    CsvSourceResolver,
    ImportReport,
    academic_year_is_reasonable,
    is_director_component,
    load_csv_rows,
    normalize_string,
    parse_optional_bool,
    parse_optional_date,
    parse_optional_datetime,
    parse_optional_int,
    write_report_files,
)

DEFAULT_IMPORT_ORDER = (
    "schools",
    "teachers",
    "students",
    "teacher_assignments",
    "student_enrollments",
)


@dataclass
class ImportContext:
    report: ImportReport
    seen_row_keys: set[str] = field(default_factory=set)
    seen_source_ids: set[int] = field(default_factory=set)
    teacher_exists_cache: dict[str, bool] = field(default_factory=dict)
    school_exists_cache: dict[str, bool] = field(default_factory=dict)
    student_exists_cache: dict[str, bool] = field(default_factory=dict)


@dataclass
class BatchImportResult:
    reports: dict[str, ImportReport]
    integrity_report: dict
    report_files: list[str]


def default_source_from_environment() -> CsvSourceResolver:
    import os

    source_dir = os.getenv("IMPORT_SOURCE_DIR")
    zip_file = os.getenv("IMPORT_ZIP_FILE")

    if source_dir:
        return CsvSourceResolver(source_dir=source_dir)
    if zip_file:
        return CsvSourceResolver(zip_file=zip_file)

    default_zip = Path("~/Downloads/data_proyecto_escuelas.zip").expanduser()
    if default_zip.exists():
        return CsvSourceResolver(zip_file=default_zip)

    default_dir = Path("app/data")
    return CsvSourceResolver(source_dir=default_dir)


def resolve_source(
    *,
    source_dir: Optional[str] = None,
    zip_file: Optional[str] = None,
) -> CsvSourceResolver:
    if source_dir or zip_file:
        return CsvSourceResolver(source_dir=source_dir, zip_file=zip_file)
    return default_source_from_environment()


def _track_duplicate(
    context: ImportContext,
    *,
    row_number: int,
    row_key: str,
    source_id: Optional[int] = None,
) -> bool:
    if source_id is not None:
        if source_id in context.seen_source_ids:
            context.report.add_issue(
                level="duplicate",
                code="duplicate_source_id",
                message="El archivo repite el identificador fuente.",
                row_number=row_number,
                row_key=str(source_id),
            )
            return True
        context.seen_source_ids.add(source_id)

    if row_key in context.seen_row_keys:
        context.report.add_issue(
            level="duplicate",
            code="duplicate_row_key",
            message="El archivo repite una clave natural ya procesada.",
            row_number=row_number,
            row_key=row_key,
        )
        return True

    context.seen_row_keys.add(row_key)
    return False


def _validate_datetime_pair(
    *,
    created_at,
    updated_at,
    report: ImportReport,
    row_number: int,
    row_key: str,
) -> None:
    if created_at and updated_at and updated_at < created_at:
        report.add_issue(
            level="warning",
            code="updated_before_created",
            message="updated_at es anterior a created_at; se conserva el valor fuente.",
            row_number=row_number,
            row_key=row_key,
        )


def _get_school_exists(db: Session, context: ImportContext, school_code: str) -> bool:
    cached = context.school_exists_cache.get(school_code)
    if cached is not None:
        return cached
    exists = db.scalar(select(School.code).where(School.code == school_code)) is not None
    context.school_exists_cache[school_code] = exists
    return exists


def _get_teacher_exists(db: Session, context: ImportContext, id_persona: str) -> bool:
    cached = context.teacher_exists_cache.get(id_persona)
    if cached is not None:
        return cached
    exists = (
        db.scalar(select(Teacher.id_persona).where(Teacher.id_persona == id_persona))
        is not None
    )
    context.teacher_exists_cache[id_persona] = exists
    return exists


def _get_student_exists(db: Session, context: ImportContext, nie: str) -> bool:
    cached = context.student_exists_cache.get(nie)
    if cached is not None:
        return cached
    exists = db.scalar(select(Student.nie).where(Student.nie == nie)) is not None
    context.student_exists_cache[nie] = exists
    return exists


def _require_value(
    value: Optional[str],
    *,
    field_name: str,
    row_number: int,
    row_key: str,
) -> str:
    if value is None:
        raise ValueError(f"El campo {field_name} es obligatorio.")
    return value


def _create_or_update_school(
    db: Session,
    context: ImportContext,
    *,
    row_number: int,
    row: dict[str, str],
) -> str:
    code = _require_value(normalize_string(row["code"]), field_name="code", row_number=row_number, row_key="")
    row_key = code
    if _track_duplicate(context, row_number=row_number, row_key=row_key):
        return "duplicate"

    name = _require_value(normalize_string(row["name"]), field_name="name", row_number=row_number, row_key=row_key)
    created_at = parse_optional_datetime(row["created_at"])
    updated_at = parse_optional_datetime(row["updated_at"])
    _validate_datetime_pair(
        created_at=created_at,
        updated_at=updated_at,
        report=context.report,
        row_number=row_number,
        row_key=row_key,
    )

    school = db.get(School, code)
    action = "updated" if school else "inserted"
    if not school:
        school = School(code=code)
        db.add(school)

    school.name = name
    school.sector = normalize_string(row["sector"])
    school.zone = normalize_string(row["zone"])
    school.department_code = parse_optional_int(row["department_code"])
    school.municipality_code = parse_optional_int(row["municipality_code"])
    if created_at:
        school.created_at = created_at
    if updated_at:
        school.updated_at = updated_at
    return action


def _create_or_update_teacher(
    db: Session,
    context: ImportContext,
    *,
    row_number: int,
    row: dict[str, str],
) -> str:
    source_id = parse_optional_int(row["id"])
    id_persona = _require_value(
        normalize_string(row["id_persona"]),
        field_name="id_persona",
        row_number=row_number,
        row_key="",
    )
    row_key = id_persona
    if _track_duplicate(
        context,
        row_number=row_number,
        row_key=row_key,
        source_id=source_id,
    ):
        return "duplicate"

    teacher = db.scalar(select(Teacher).where(Teacher.id_persona == id_persona))
    if teacher is None and source_id is not None:
        teacher_by_id = db.get(Teacher, source_id)
        if teacher_by_id and teacher_by_id.id_persona != id_persona:
            raise ValueError(
                f"Conflicto entre id fuente={source_id} e id_persona={id_persona}."
            )
        teacher = teacher_by_id

    action = "updated" if teacher else "inserted"
    if not teacher:
        teacher = Teacher(id=source_id, id_persona=id_persona)
        db.add(teacher)

    created_at = parse_optional_datetime(row["created_at"])
    updated_at = parse_optional_datetime(row["updated_at"])
    _validate_datetime_pair(
        created_at=created_at,
        updated_at=updated_at,
        report=context.report,
        row_number=row_number,
        row_key=row_key,
    )

    teacher.nip = normalize_string(row["nip"])
    teacher.dui = normalize_string(row["dui"])
    teacher.first_names = normalize_string(row["first_names"])
    teacher.last_names = normalize_string(row["last_names"])
    teacher.gender = normalize_string(row["gender"])
    teacher.specialty = normalize_string(row["specialty"])
    if created_at:
        teacher.created_at = created_at
    if updated_at:
        teacher.updated_at = updated_at
    return action


def _validate_academic_year(
    *,
    academic_year: int,
    report: ImportReport,
    row_number: int,
    row_key: str,
) -> None:
    if academic_year_is_reasonable(academic_year):
        return
    report.invalid_year_rows += 1
    raise ValueError(f"Año académico fuera de rango razonable: {academic_year}.")


def _maybe_warn_assignment_scope(
    *,
    report: ImportReport,
    row_number: int,
    row_key: str,
    component_type: Optional[str],
    grade_label: Optional[str],
    section_id: Optional[str],
    section_name: Optional[str],
) -> None:
    if is_director_component(component_type):
        report.director_rows += 1
        return
    if grade_label is None:
        report.add_issue(
            level="warning",
            code="assignment_missing_grade_label",
            message="La asignación no trae grade_label.",
            row_number=row_number,
            row_key=row_key,
        )
    if section_id is None and section_name is None:
        report.add_issue(
            level="warning",
            code="assignment_missing_section",
            message="La asignación no trae section_id ni section_name.",
            row_number=row_number,
            row_key=row_key,
        )


def _create_or_update_teacher_assignment(
    db: Session,
    context: ImportContext,
    *,
    row_number: int,
    row: dict[str, str],
) -> str:
    source_id = parse_optional_int(row["id"])
    id_persona = _require_value(
        normalize_string(row["id_persona"]),
        field_name="id_persona",
        row_number=row_number,
        row_key="",
    )
    school_code = _require_value(
        normalize_string(row["school_code"]),
        field_name="school_code",
        row_number=row_number,
        row_key=id_persona,
    )
    academic_year = parse_optional_int(row["academic_year"])
    if academic_year is None:
        raise ValueError("El campo academic_year es obligatorio.")

    section_id = normalize_string(row["section_id"])
    row_key = f"{id_persona}|{school_code}|{academic_year}|{section_id or '__NULL__'}"
    if _track_duplicate(
        context,
        row_number=row_number,
        row_key=row_key,
        source_id=source_id,
    ):
        return "duplicate"

    _validate_academic_year(
        academic_year=academic_year,
        report=context.report,
        row_number=row_number,
        row_key=row_key,
    )

    if not _get_teacher_exists(db, context, id_persona):
        context.report.invalid_relation_rows += 1
        raise ValueError(f"No existe teachers.id_persona={id_persona}.")
    if not _get_school_exists(db, context, school_code):
        context.report.invalid_relation_rows += 1
        raise ValueError(f"No existe schools.code={school_code}.")

    component_type = normalize_string(row["component_type"])
    grade_label = normalize_string(row["grade_label"])
    section_name = normalize_string(row["section_name"])
    shift = normalize_string(row["shift"])
    cod_adscrito = normalize_string(row["cod_adscrito"])

    _maybe_warn_assignment_scope(
        report=context.report,
        row_number=row_number,
        row_key=row_key,
        component_type=component_type,
        grade_label=grade_label,
        section_id=section_id,
        section_name=section_name,
    )

    assignment = db.get(TeacherAssignment, source_id) if source_id is not None else None
    if assignment is None:
        assignment_query = select(TeacherAssignment).where(
            TeacherAssignment.id_persona == id_persona,
            TeacherAssignment.school_code == school_code,
            TeacherAssignment.academic_year == academic_year,
        )
        if section_id is None:
            assignment_query = assignment_query.where(TeacherAssignment.section_id.is_(None))
        else:
            assignment_query = assignment_query.where(
                TeacherAssignment.section_id == section_id
            )
        assignment = db.scalar(assignment_query)

    action = "updated" if assignment else "inserted"
    if not assignment:
        assignment = TeacherAssignment(
            id=source_id,
            id_persona=id_persona,
            school_code=school_code,
            academic_year=academic_year,
        )
        db.add(assignment)

    created_at = parse_optional_datetime(row["created_at"])
    updated_at = parse_optional_datetime(row["updated_at"])
    _validate_datetime_pair(
        created_at=created_at,
        updated_at=updated_at,
        report=context.report,
        row_number=row_number,
        row_key=row_key,
    )

    assignment.id_persona = id_persona
    assignment.school_code = school_code
    assignment.academic_year = academic_year
    assignment.component_type = component_type
    assignment.grade_label = grade_label
    assignment.section_id = section_id
    assignment.section_name = section_name
    assignment.shift = shift
    assignment.cod_adscrito = cod_adscrito
    if created_at:
        assignment.created_at = created_at
    if updated_at:
        assignment.updated_at = updated_at
    return action


def _create_or_update_student(
    db: Session,
    context: ImportContext,
    *,
    row_number: int,
    row: dict[str, str],
) -> str:
    source_id = parse_optional_int(row["id"])
    nie = _require_value(
        normalize_string(row["nie"]),
        field_name="nie",
        row_number=row_number,
        row_key="",
    )
    row_key = nie
    if _track_duplicate(
        context,
        row_number=row_number,
        row_key=row_key,
        source_id=source_id,
    ):
        return "duplicate"

    student = db.scalar(select(Student).where(Student.nie == nie))
    if student is None and source_id is not None:
        student_by_id = db.get(Student, source_id)
        if student_by_id and student_by_id.nie != nie:
            raise ValueError(f"Conflicto entre id fuente={source_id} y nie={nie}.")
        student = student_by_id

    action = "updated" if student else "inserted"
    if not student:
        student = Student(id=source_id, nie=nie)
        db.add(student)

    created_at = parse_optional_datetime(row["created_at"])
    updated_at = parse_optional_datetime(row["updated_at"])
    _validate_datetime_pair(
        created_at=created_at,
        updated_at=updated_at,
        report=context.report,
        row_number=row_number,
        row_key=row_key,
    )

    birth_date = None
    raw_birth_date = normalize_string(row["birth_date"])
    if raw_birth_date:
        try:
            birth_date = parse_optional_date(raw_birth_date)
        except ValueError:
            context.report.add_issue(
                level="warning",
                code="invalid_birth_date",
                message=(
                    "birth_date no tiene formato YYYY-MM-DD y se importara como NULL "
                    "para no corromper la columna date."
                ),
                row_number=row_number,
                row_key=row_key,
            )

    student.gender = normalize_string(row["gender"])
    student.first_name1 = normalize_string(row["first_name1"])
    student.first_name2 = normalize_string(row["first_name2"])
    student.first_name3 = normalize_string(row["first_name3"])
    student.last_name1 = normalize_string(row["last_name1"])
    student.last_name2 = normalize_string(row["last_name2"])
    student.last_name3 = normalize_string(row["last_name3"])
    student.birth_date = birth_date
    student.age_current = parse_optional_int(row["age_current"])
    student.is_manual = bool(parse_optional_bool(row["is_manual"]) or False)
    student.father_full_name = normalize_string(row["father_full_name"])
    student.mother_full_name = normalize_string(row["mother_full_name"])
    student.address_full = normalize_string(row["address_full"])
    if created_at:
        student.created_at = created_at
    if updated_at:
        student.updated_at = updated_at
    return action


def _maybe_warn_enrollment_scope(
    *,
    report: ImportReport,
    row_number: int,
    row_key: str,
    grade_label: Optional[str],
    section_code: Optional[str],
    modality: Optional[str],
    submodality: Optional[str],
) -> None:
    if grade_label is None:
        report.add_issue(
            level="warning",
            code="enrollment_missing_grade_label",
            message="La matricula no trae grade_label.",
            row_number=row_number,
            row_key=row_key,
        )
    if section_code is None:
        report.add_issue(
            level="warning",
            code="enrollment_missing_section_code",
            message="La matricula no trae section_code.",
            row_number=row_number,
            row_key=row_key,
        )
    if submodality and not modality:
        report.add_issue(
            level="warning",
            code="enrollment_submodality_without_modality",
            message="Se recibio submodality sin modality.",
            row_number=row_number,
            row_key=row_key,
        )


def _create_or_update_student_enrollment(
    db: Session,
    context: ImportContext,
    *,
    row_number: int,
    row: dict[str, str],
) -> str:
    source_id = parse_optional_int(row["id"])
    nie = _require_value(
        normalize_string(row["nie"]),
        field_name="nie",
        row_number=row_number,
        row_key="",
    )
    school_code = _require_value(
        normalize_string(row["school_code"]),
        field_name="school_code",
        row_number=row_number,
        row_key=nie,
    )
    academic_year = parse_optional_int(row["academic_year"])
    if academic_year is None:
        raise ValueError("El campo academic_year es obligatorio.")

    row_key = f"{nie}|{school_code}|{academic_year}"
    if _track_duplicate(
        context,
        row_number=row_number,
        row_key=row_key,
        source_id=source_id,
    ):
        return "duplicate"

    _validate_academic_year(
        academic_year=academic_year,
        report=context.report,
        row_number=row_number,
        row_key=row_key,
    )

    if not _get_student_exists(db, context, nie):
        context.report.invalid_relation_rows += 1
        raise ValueError(f"No existe students.nie={nie}.")
    if not _get_school_exists(db, context, school_code):
        context.report.invalid_relation_rows += 1
        raise ValueError(f"No existe schools.code={school_code}.")

    grade_label = normalize_string(row["grade_label"])
    section_code = normalize_string(row["section_code"])
    modality = normalize_string(row["modality"])
    submodality = normalize_string(row["submodality"])

    _maybe_warn_enrollment_scope(
        report=context.report,
        row_number=row_number,
        row_key=row_key,
        grade_label=grade_label,
        section_code=section_code,
        modality=modality,
        submodality=submodality,
    )

    enrollment = db.get(StudentEnrollment, source_id) if source_id is not None else None
    if enrollment is None:
        enrollment = db.scalar(
            select(StudentEnrollment).where(
                StudentEnrollment.nie == nie,
                StudentEnrollment.school_code == school_code,
                StudentEnrollment.academic_year == academic_year,
            )
        )

    action = "updated" if enrollment else "inserted"
    if not enrollment:
        enrollment = StudentEnrollment(
            id=source_id,
            nie=nie,
            school_code=school_code,
            academic_year=academic_year,
        )
        db.add(enrollment)

    created_at = parse_optional_datetime(row["created_at"])
    updated_at = parse_optional_datetime(row["updated_at"])
    _validate_datetime_pair(
        created_at=created_at,
        updated_at=updated_at,
        report=context.report,
        row_number=row_number,
        row_key=row_key,
    )

    enrollment.nie = nie
    enrollment.school_code = school_code
    enrollment.academic_year = academic_year
    enrollment.section_code = section_code
    enrollment.grade_label = grade_label
    enrollment.modality = modality
    enrollment.submodality = submodality
    if created_at:
        enrollment.created_at = created_at
    if updated_at:
        enrollment.updated_at = updated_at
    return action


ROW_HANDLERS: dict[str, Callable[..., str]] = {
    "schools": _create_or_update_school,
    "teachers": _create_or_update_teacher,
    "teacher_assignments": _create_or_update_teacher_assignment,
    "students": _create_or_update_student,
    "student_enrollments": _create_or_update_student_enrollment,
}


def import_dataset(
    db: Session,
    dataset: str,
    *,
    resolver: CsvSourceResolver,
    batch_size: int = 500,
    dry_run: bool = False,
    commit_each_batch: Optional[bool] = None,
    rollback_at_end: Optional[bool] = None,
    commit_at_end: Optional[bool] = None,
) -> ImportReport:
    if dataset not in CSV_SPECS:
        raise ValueError(f"Dataset no soportado: {dataset}")

    spec = CSV_SPECS[dataset]
    report = ImportReport(dataset=spec.dataset, source_name=resolver.describe(spec.filename))
    context = ImportContext(report=report)
    row_handler = ROW_HANDLERS[dataset]
    pending_in_batch = 0
    commit_each_batch = (not dry_run) if commit_each_batch is None else commit_each_batch
    rollback_at_end = dry_run if rollback_at_end is None else rollback_at_end
    commit_at_end = (not rollback_at_end) if commit_at_end is None else commit_at_end
    outer_savepoint = db.begin_nested() if rollback_at_end else None

    try:
        for row_number, row in load_csv_rows(resolver, spec):
            report.total_rows += 1
            try:
                with db.begin_nested():
                    action = row_handler(
                        db,
                        context,
                        row_number=row_number,
                        row=row,
                    )
                    report.record_action(action)
                    db.flush()
            except (ValueError, SQLAlchemyError) as exc:
                report.add_issue(
                    level="error",
                    code="row_validation_error",
                    message=str(exc),
                    row_number=row_number,
                )
            pending_in_batch += 1
            if pending_in_batch >= batch_size and commit_each_batch:
                if rollback_at_end:
                    db.flush()
                else:
                    db.commit()
                pending_in_batch = 0

        if rollback_at_end:
            if outer_savepoint and outer_savepoint.is_active:
                outer_savepoint.rollback()
            else:
                db.rollback()
            db.expire_all()
            db.expunge_all()
        elif commit_at_end and (pending_in_batch or commit_each_batch):
            db.commit()
    except CsvHeaderError as exc:
        if outer_savepoint and outer_savepoint.is_active:
            outer_savepoint.rollback()
        db.rollback()
        db.expunge_all()
        report.add_issue(level="error", code="invalid_headers", message=str(exc))
    finally:
        report.finish()

    return report


def import_schools(
    db: Session,
    *,
    resolver: CsvSourceResolver,
    batch_size: int = 500,
    dry_run: bool = False,
) -> ImportReport:
    return import_dataset(
        db,
        "schools",
        resolver=resolver,
        batch_size=batch_size,
        dry_run=dry_run,
    )


def import_teachers(
    db: Session,
    *,
    resolver: CsvSourceResolver,
    batch_size: int = 500,
    dry_run: bool = False,
) -> ImportReport:
    return import_dataset(
        db,
        "teachers",
        resolver=resolver,
        batch_size=batch_size,
        dry_run=dry_run,
    )


def import_teacher_assignments(
    db: Session,
    *,
    resolver: CsvSourceResolver,
    batch_size: int = 500,
    dry_run: bool = False,
) -> ImportReport:
    return import_dataset(
        db,
        "teacher_assignments",
        resolver=resolver,
        batch_size=batch_size,
        dry_run=dry_run,
    )


def import_students(
    db: Session,
    *,
    resolver: CsvSourceResolver,
    batch_size: int = 500,
    dry_run: bool = False,
) -> ImportReport:
    return import_dataset(
        db,
        "students",
        resolver=resolver,
        batch_size=batch_size,
        dry_run=dry_run,
    )


def import_student_enrollments(
    db: Session,
    *,
    resolver: CsvSourceResolver,
    batch_size: int = 500,
    dry_run: bool = False,
) -> ImportReport:
    return import_dataset(
        db,
        "student_enrollments",
        resolver=resolver,
        batch_size=batch_size,
        dry_run=dry_run,
    )


def audit_legacy_integrity(db: Session) -> dict:
    current_year = date.today().year

    assignment_missing_teachers = db.scalar(
        select(func.count())
        .select_from(TeacherAssignment)
        .outerjoin(Teacher, Teacher.id_persona == TeacherAssignment.id_persona)
        .where(Teacher.id.is_(None))
    )
    assignment_missing_schools = db.scalar(
        select(func.count())
        .select_from(TeacherAssignment)
        .outerjoin(School, School.code == TeacherAssignment.school_code)
        .where(School.code.is_(None))
    )
    enrollment_missing_students = db.scalar(
        select(func.count())
        .select_from(StudentEnrollment)
        .outerjoin(Student, Student.nie == StudentEnrollment.nie)
        .where(Student.id.is_(None))
    )
    enrollment_missing_schools = db.scalar(
        select(func.count())
        .select_from(StudentEnrollment)
        .outerjoin(School, School.code == StudentEnrollment.school_code)
        .where(School.code.is_(None))
    )
    assignment_invalid_years = db.scalar(
        select(func.count())
        .select_from(TeacherAssignment)
        .where(
            or_(
                TeacherAssignment.academic_year < 2000,
                TeacherAssignment.academic_year > current_year + 2,
            )
        )
    )
    enrollment_invalid_years = db.scalar(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(
            or_(
                StudentEnrollment.academic_year < 2000,
                StudentEnrollment.academic_year > current_year + 2,
            )
        )
    )
    director_assignments = db.scalar(
        select(func.count())
        .select_from(TeacherAssignment)
        .where(TeacherAssignment.component_type.ilike("%DIRECTOR%"))
    )
    assignments_missing_scope = db.scalar(
        select(func.count())
        .select_from(TeacherAssignment)
        .where(
            ~TeacherAssignment.component_type.ilike("%DIRECTOR%"),
            TeacherAssignment.grade_label.is_(None),
            TeacherAssignment.section_id.is_(None),
            TeacherAssignment.section_name.is_(None),
        )
    )
    enrollments_missing_scope = db.scalar(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(
            or_(
                StudentEnrollment.grade_label.is_(None),
                StudentEnrollment.section_code.is_(None),
            )
        )
    )

    status = "ok"
    critical_total = (
        (assignment_missing_teachers or 0)
        + (assignment_missing_schools or 0)
        + (enrollment_missing_students or 0)
        + (enrollment_missing_schools or 0)
        + (assignment_invalid_years or 0)
        + (enrollment_invalid_years or 0)
    )
    if critical_total:
        status = "issues_detected"

    return {
        "status": status,
        "teacher_assignments_missing_teachers": assignment_missing_teachers or 0,
        "teacher_assignments_missing_schools": assignment_missing_schools or 0,
        "student_enrollments_missing_students": enrollment_missing_students or 0,
        "student_enrollments_missing_schools": enrollment_missing_schools or 0,
        "teacher_assignments_invalid_years": assignment_invalid_years or 0,
        "student_enrollments_invalid_years": enrollment_invalid_years or 0,
        "director_assignments": director_assignments or 0,
        "teacher_assignments_missing_scope": assignments_missing_scope or 0,
        "student_enrollments_missing_scope": enrollments_missing_scope or 0,
    }


def import_all_datasets(
    db: Session,
    *,
    resolver: CsvSourceResolver,
    batch_size: int = 500,
    dry_run: bool = False,
    report_dir: str | Path = "logs/imports",
    filename_prefix: Optional[str] = None,
) -> BatchImportResult:
    active_db = db
    outer_savepoint = active_db.begin_nested() if dry_run else None
    reports: dict[str, ImportReport] = {}
    report_files: list[str] = []

    try:
        for dataset in DEFAULT_IMPORT_ORDER:
            report = import_dataset(
                active_db,
                dataset,
                resolver=resolver,
                batch_size=batch_size,
                dry_run=False,
                commit_each_batch=False,
                rollback_at_end=False,
                commit_at_end=False,
            )
            reports[dataset] = report
            json_path, txt_path = write_report_files(
                report,
                report_dir=report_dir,
                filename_prefix=filename_prefix,
            )
            report_files.extend([str(json_path), str(txt_path)])

        integrity_report = audit_legacy_integrity(active_db)
        if dry_run:
            if outer_savepoint and outer_savepoint.is_active:
                outer_savepoint.rollback()
            else:
                active_db.rollback()
            active_db.expire_all()
            active_db.expunge_all()
        return BatchImportResult(
            reports=reports,
            integrity_report=integrity_report,
            report_files=report_files,
        )
    finally:
        if dry_run and outer_savepoint and outer_savepoint.is_active:
            outer_savepoint.rollback()
