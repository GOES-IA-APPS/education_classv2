import csv
import io
import zipfile

from sqlalchemy import func, select

from app.models import School, Student, StudentEnrollment, Teacher, TeacherAssignment
from app.services.import_service import import_all_datasets, import_dataset
from app.utils.importing import CSV_SPECS, CsvSourceResolver, load_csv_rows


def write_csv(path, headers, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        writer.writerows(rows)


def build_valid_source_dir(tmp_path):
    source_dir = tmp_path / "csvs"
    source_dir.mkdir()

    write_csv(
        source_dir / CSV_SPECS["schools"].filename,
        CSV_SPECS["schools"].headers,
        [
            ["SCH-001", "Centro Escolar Uno", "PUBLICO", "URBANA", 1, 101, "2026-01-16 00:55:36", "2026-01-19 21:18:25"],
        ],
    )
    write_csv(
        source_dir / CSV_SPECS["teachers"].filename,
        CSV_SPECS["teachers"].headers,
        [
            [10, "DOC-001", "12345", "99999999-9", "Ana", "Martinez", "Femenino", "Matematica", "", ""],
        ],
    )
    write_csv(
        source_dir / CSV_SPECS["students"].filename,
        CSV_SPECS["students"].headers,
        [
            [20, "NIE-001", "Hombre", "Carlos", "", "", "Lopez", "", "", "16", 12, 0, "", "", "", "2026-01-16 00:56:05", "2026-01-16 16:11:34"],
        ],
    )
    write_csv(
        source_dir / CSV_SPECS["teacher_assignments"].filename,
        CSV_SPECS["teacher_assignments"].headers,
        [
            [30, "DOC-001", "SCH-001", 2026, "DIRECTOR", "", "", "", "", "", "2026-01-16 00:55:36", "2026-01-17 05:36:26"],
        ],
    )
    write_csv(
        source_dir / CSV_SPECS["student_enrollments"].filename,
        CSV_SPECS["student_enrollments"].headers,
        [
            [40, "NIE-001", "SCH-001", 2026, "SEC-A", "Sexto Grado", "Regular", "Regular", "2026-01-16 00:56:05", "2026-01-16 16:11:34"],
        ],
    )
    return source_dir


def test_csv_reader_supports_zip_source(tmp_path):
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_SPECS["schools"].headers)
    writer.writerow(
        ["SCH-ZIP", "Centro Escolar Zip", "PUBLICO", "URBANA", 1, 101, "", ""]
    )

    zip_path = tmp_path / "legacy.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(f"edu_data/{CSV_SPECS['schools'].filename}", csv_buffer.getvalue())

    resolver = CsvSourceResolver(zip_file=zip_path)
    rows = list(load_csv_rows(resolver, CSV_SPECS["schools"]))

    assert len(rows) == 1
    assert rows[0][1]["code"] == "SCH-ZIP"


def test_import_dataset_rejects_invalid_headers(tmp_path, db_session):
    source_dir = tmp_path / "csvs"
    source_dir.mkdir()
    write_csv(
        source_dir / CSV_SPECS["schools"].filename,
        ["wrong", "headers"],
        [["1", "x"]],
    )

    report = import_dataset(
        db_session,
        "schools",
        resolver=CsvSourceResolver(source_dir=source_dir),
    )

    assert report.errors == 1
    assert report.issue_counts["invalid_headers"] == 1
    assert db_session.scalar(select(func.count()).select_from(School)) == 0


def test_import_all_is_idempotent_and_preserves_relations(tmp_path, db_session):
    source_dir = build_valid_source_dir(tmp_path)
    report_dir = tmp_path / "reports"

    first_result = import_all_datasets(
        db_session,
        resolver=CsvSourceResolver(source_dir=source_dir),
        batch_size=2,
        report_dir=report_dir,
        filename_prefix="phase4a",
    )
    second_result = import_all_datasets(
        db_session,
        resolver=CsvSourceResolver(source_dir=source_dir),
        batch_size=2,
        report_dir=report_dir,
        filename_prefix="phase4b",
    )

    assert first_result.integrity_report["status"] == "ok"
    assert second_result.integrity_report["status"] == "ok"
    assert db_session.scalar(select(func.count()).select_from(School)) == 1
    assert db_session.scalar(select(func.count()).select_from(Teacher)) == 1
    assert db_session.scalar(select(func.count()).select_from(Student)) == 1
    assert db_session.scalar(select(func.count()).select_from(TeacherAssignment)) == 1
    assert db_session.scalar(select(func.count()).select_from(StudentEnrollment)) == 1

    student = db_session.scalar(select(Student).where(Student.nie == "NIE-001"))
    assert student is not None
    assert student.birth_date is None
    assert first_result.reports["students"].issue_counts["invalid_birth_date"] == 1
    assert second_result.reports["students"].updated == 1
    assert (report_dir / "phase4a_schools.json").exists()
    assert (report_dir / "phase4b_student_enrollments.txt").exists()


def test_imports_detect_invalid_relations_and_dry_run_rolls_back(tmp_path, db_session):
    source_dir = tmp_path / "csvs"
    source_dir.mkdir()

    write_csv(
        source_dir / CSV_SPECS["schools"].filename,
        CSV_SPECS["schools"].headers,
        [
            ["SCH-002", "Centro Escolar Dos", "PUBLICO", "RURAL", 2, 202, "", ""],
        ],
    )
    write_csv(
        source_dir / CSV_SPECS["teachers"].filename,
        CSV_SPECS["teachers"].headers,
        [],
    )
    write_csv(
        source_dir / CSV_SPECS["students"].filename,
        CSV_SPECS["students"].headers,
        [],
    )
    write_csv(
        source_dir / CSV_SPECS["teacher_assignments"].filename,
        CSV_SPECS["teacher_assignments"].headers,
        [
            [50, "DOC-MISSING", "SCH-002", 2026, "DOCENTE", "Sexto Grado", "A", "A", "MANANA", "", "", ""],
        ],
    )
    write_csv(
        source_dir / CSV_SPECS["student_enrollments"].filename,
        CSV_SPECS["student_enrollments"].headers,
        [
            [60, "NIE-MISSING", "SCH-002", 2026, "A", "Sexto Grado", "Regular", "Regular", "", ""],
        ],
    )

    result = import_all_datasets(
        db_session,
        resolver=CsvSourceResolver(source_dir=source_dir),
        batch_size=10,
        dry_run=True,
        report_dir=tmp_path / "reports",
        filename_prefix="dryrun",
    )

    assert result.reports["teacher_assignments"].errors == 1
    assert result.reports["teacher_assignments"].invalid_relation_rows == 1
    assert result.reports["student_enrollments"].errors == 1
    assert result.reports["student_enrollments"].invalid_relation_rows == 1
    assert db_session.scalar(select(func.count()).select_from(School)) == 0
    assert db_session.scalar(select(func.count()).select_from(TeacherAssignment)) == 0
    assert db_session.scalar(select(func.count()).select_from(StudentEnrollment)) == 0
