from __future__ import annotations

import csv
import io
import json
import zipfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional, TextIO


NULL_LITERALS = {"", "null", "none", "n/a", "na", "nil"}


@dataclass(frozen=True)
class CsvFileSpec:
    dataset: str
    filename: str
    headers: tuple[str, ...]


CSV_SPECS = {
    "schools": CsvFileSpec(
        dataset="schools",
        filename="school_db_05022026.csv",
        headers=(
            "code",
            "name",
            "sector",
            "zone",
            "department_code",
            "municipality_code",
            "created_at",
            "updated_at",
        ),
    ),
    "teachers": CsvFileSpec(
        dataset="teachers",
        filename="teacher_db_05022026.csv",
        headers=(
            "id",
            "id_persona",
            "nip",
            "dui",
            "first_names",
            "last_names",
            "gender",
            "specialty",
            "created_at",
            "updated_at",
        ),
    ),
    "teacher_assignments": CsvFileSpec(
        dataset="teacher_assignments",
        filename="teacher_assignments_db_05022026.csv",
        headers=(
            "id",
            "id_persona",
            "school_code",
            "academic_year",
            "component_type",
            "grade_label",
            "section_id",
            "section_name",
            "shift",
            "cod_adscrito",
            "created_at",
            "updated_at",
        ),
    ),
    "students": CsvFileSpec(
        dataset="students",
        filename="estudent_db_05022026.csv",
        headers=(
            "id",
            "nie",
            "gender",
            "first_name1",
            "first_name2",
            "first_name3",
            "last_name1",
            "last_name2",
            "last_name3",
            "birth_date",
            "age_current",
            "is_manual",
            "father_full_name",
            "mother_full_name",
            "address_full",
            "created_at",
            "updated_at",
        ),
    ),
    "student_enrollments": CsvFileSpec(
        dataset="student_enrollments",
        filename="estudent_enrollments_db_05022026.csv",
        headers=(
            "id",
            "nie",
            "school_code",
            "academic_year",
            "section_code",
            "grade_label",
            "modality",
            "submodality",
            "created_at",
            "updated_at",
        ),
    ),
}


@dataclass
class ImportIssue:
    level: str
    code: str
    message: str
    row_number: Optional[int] = None
    row_key: Optional[str] = None


@dataclass
class ImportReport:
    dataset: str
    source_name: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    total_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    duplicates: int = 0
    errors: int = 0
    warnings: int = 0
    invalid_relation_rows: int = 0
    invalid_year_rows: int = 0
    director_rows: int = 0
    issue_counts: dict[str, int] = field(default_factory=dict)
    issues: list[ImportIssue] = field(default_factory=list)
    max_issue_samples: int = 200

    def record_action(self, action: str) -> None:
        if action == "inserted":
            self.inserted += 1
        elif action == "updated":
            self.updated += 1
        elif action == "skipped":
            self.skipped += 1

    def add_issue(
        self,
        *,
        level: str,
        code: str,
        message: str,
        row_number: Optional[int] = None,
        row_key: Optional[str] = None,
    ) -> None:
        self.issue_counts[code] = self.issue_counts.get(code, 0) + 1
        if level == "error":
            self.errors += 1
        elif level == "warning":
            self.warnings += 1
        elif level == "duplicate":
            self.duplicates += 1
            self.skipped += 1
        if len(self.issues) < self.max_issue_samples:
            self.issues.append(
                ImportIssue(
                    level=level,
                    code=code,
                    message=message,
                    row_number=row_number,
                    row_key=row_key,
                )
            )

    def finish(self) -> None:
        self.finished_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "source_name": self.source_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_rows": self.total_rows,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "warnings": self.warnings,
            "invalid_relation_rows": self.invalid_relation_rows,
            "invalid_year_rows": self.invalid_year_rows,
            "director_rows": self.director_rows,
            "issue_counts": self.issue_counts,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def render_summary(self) -> str:
        lines = [
            f"Dataset: {self.dataset}",
            f"Fuente: {self.source_name}",
            f"Inicio: {self.started_at.isoformat()}",
            f"Fin: {self.finished_at.isoformat() if self.finished_at else 'N/A'}",
            f"Filas leidas: {self.total_rows}",
            f"Insertadas: {self.inserted}",
            f"Actualizadas: {self.updated}",
            f"Ignoradas: {self.skipped}",
            f"Duplicados: {self.duplicates}",
            f"Errores: {self.errors}",
            f"Advertencias: {self.warnings}",
            f"Relaciones invalidas: {self.invalid_relation_rows}",
            f"Anios invalidos: {self.invalid_year_rows}",
            f"Filas director: {self.director_rows}",
        ]
        if self.issue_counts:
            lines.append("Conteo de incidencias:")
            for code, count in sorted(self.issue_counts.items()):
                lines.append(f"- {code}: {count}")
        if self.issues:
            lines.append("Muestras:")
            for issue in self.issues:
                lines.append(
                    f"- [{issue.level}] {issue.code} fila={issue.row_number} clave={issue.row_key}: {issue.message}"
                )
        return "\n".join(lines)


class CsvHeaderError(ValueError):
    pass


class CsvSourceResolver:
    def __init__(
        self,
        *,
        source_dir: Optional[str | Path] = None,
        zip_file: Optional[str | Path] = None,
    ) -> None:
        if bool(source_dir) == bool(zip_file):
            raise ValueError("Debes indicar exactamente uno entre source_dir o zip_file.")
        self.source_dir = Path(source_dir).expanduser() if source_dir else None
        self.zip_file = Path(zip_file).expanduser() if zip_file else None

    @property
    def label(self) -> str:
        if self.source_dir:
            return str(self.source_dir)
        if self.zip_file:
            return str(self.zip_file)
        return "desconocido"

    def describe(self, filename: str) -> str:
        return f"{self.label}:{filename}"

    @contextmanager
    def open_text(self, filename: str) -> Iterator[TextIO]:
        if self.source_dir:
            path = self.source_dir / filename
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                yield handle
            return

        if not self.zip_file:
            raise FileNotFoundError(filename)

        with zipfile.ZipFile(self.zip_file) as archive:
            member_name = self._resolve_member_name(archive, filename)
            with archive.open(member_name) as raw_handle:
                with io.TextIOWrapper(
                    raw_handle,
                    encoding="utf-8-sig",
                    newline="",
                ) as handle:
                    yield handle

    def _resolve_member_name(self, archive: zipfile.ZipFile, filename: str) -> str:
        names = archive.namelist()
        for name in names:
            if name == filename or name.endswith(f"/{filename}"):
                return name
        raise FileNotFoundError(f"No se encontro {filename} dentro de {self.zip_file}.")


def normalize_string(value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    if normalized.strip('"').strip().lower() in NULL_LITERALS:
        return None
    return normalized


def parse_optional_int(value: object) -> Optional[int]:
    normalized = normalize_string(value)
    if normalized is None:
        return None
    return int(normalized)


def parse_optional_bool(value: object) -> Optional[bool]:
    normalized = normalize_string(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if lowered in {"1", "true", "yes", "si", "sí"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    raise ValueError(f"Valor booleano invalido: {value}")


def parse_optional_datetime(value: object) -> Optional[datetime]:
    normalized = normalize_string(value)
    if normalized is None:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    raise ValueError(f"Fecha y hora invalida: {value}")


def parse_optional_date(value: object) -> Optional[date]:
    normalized = normalize_string(value)
    if normalized is None:
        return None
    return datetime.strptime(normalized, "%Y-%m-%d").date()


def academic_year_is_reasonable(value: int, *, reference_year: Optional[int] = None) -> bool:
    year = reference_year or date.today().year
    return 2000 <= value <= year + 2


def is_director_component(value: object) -> bool:
    normalized = normalize_string(value)
    if normalized is None:
        return False
    return "DIRECTOR" in normalized.upper()


def load_csv_rows(
    resolver: CsvSourceResolver,
    spec: CsvFileSpec,
) -> Iterator[tuple[int, dict[str, str]]]:
    with resolver.open_text(spec.filename) as handle:
        reader = csv.DictReader(handle, delimiter=";")
        headers = tuple(reader.fieldnames or ())
        if headers != spec.headers:
            raise CsvHeaderError(
                f"Encabezados invalidos para {spec.filename}. "
                f"Esperados={list(spec.headers)} obtenidos={list(headers)}"
            )
        for line_number, row in enumerate(reader, start=2):
            yield line_number, {key: value or "" for key, value in row.items()}


def ensure_report_dir(path: str | Path) -> Path:
    report_dir = Path(path)
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_report_files(
    report: ImportReport,
    *,
    report_dir: str | Path,
    filename_prefix: Optional[str] = None,
) -> tuple[Path, Path]:
    report.finish()
    safe_prefix = filename_prefix or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    report_dir_path = ensure_report_dir(report_dir)
    json_path = report_dir_path / f"{safe_prefix}_{report.dataset}.json"
    txt_path = report_dir_path / f"{safe_prefix}_{report.dataset}.txt"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    txt_path.write_text(report.render_summary(), encoding="utf-8")
    return json_path, txt_path
