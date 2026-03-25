from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Optional

from app.db import Base, SessionLocal, engine
from app.services.import_service import (
    audit_legacy_integrity,
    import_all_datasets,
    import_dataset,
    resolve_source,
)
from app.utils.importing import ensure_report_dir


def build_common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--source-dir", help="Directorio que contiene los CSV heredados.")
    parser.add_argument(
        "--zip-file",
        help="ZIP que contiene los CSV heredados, por ejemplo ~/Downloads/data_proyecto_escuelas.zip.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Cantidad de filas por lote antes de confirmar cambios.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida e importa en transacción temporal; al final hace rollback.",
    )
    parser.add_argument(
        "--report-dir",
        default="logs/imports",
        help="Directorio donde se guardan reportes JSON y TXT.",
    )
    parser.add_argument(
        "--prefix",
        default=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        help="Prefijo para nombrar archivos de reporte.",
    )
    return parser


def _print_report(report, *, integrity_report: Optional[dict] = None) -> None:
    print(report.render_summary())
    if integrity_report is not None:
        print("")
        print("Auditoria de integridad:")
        print(json.dumps(integrity_report, indent=2, ensure_ascii=False))


def _write_combined_report(batch_result, *, report_dir: str, prefix: str) -> str:
    output_dir = ensure_report_dir(report_dir)
    combined_path = output_dir / f"{prefix}_import_all.json"
    combined_payload = {
        "reports": {dataset: report.to_dict() for dataset, report in batch_result.reports.items()},
        "integrity_report": batch_result.integrity_report,
        "report_files": batch_result.report_files,
    }
    combined_path.write_text(
        json.dumps(combined_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(combined_path)


def run_single_dataset_cli(dataset: str) -> int:
    parser = build_common_parser(f"Importador seguro para {dataset}.")
    args = parser.parse_args()

    resolver = resolve_source(source_dir=args.source_dir, zip_file=args.zip_file)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        report = import_dataset(
            db,
            dataset,
            resolver=resolver,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
        integrity_report = audit_legacy_integrity(db)
        from app.utils.importing import write_report_files

        json_path, txt_path = write_report_files(
            report,
            report_dir=args.report_dir,
            filename_prefix=args.prefix,
        )
        _print_report(report, integrity_report=integrity_report)
        print("")
        print(f"Reportes: {json_path} | {txt_path}")
        return 0 if report.errors == 0 else 1
    finally:
        db.close()


def run_import_all_cli() -> int:
    parser = build_common_parser("Importa todos los CSV heredados de forma segura.")
    args = parser.parse_args()

    resolver = resolve_source(source_dir=args.source_dir, zip_file=args.zip_file)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        batch_result = import_all_datasets(
            db,
            resolver=resolver,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            report_dir=args.report_dir,
            filename_prefix=args.prefix,
        )
        for dataset in batch_result.reports:
            _print_report(batch_result.reports[dataset])
            print("")
        print("Auditoria de integridad final:")
        print(json.dumps(batch_result.integrity_report, indent=2, ensure_ascii=False))
        combined_path = _write_combined_report(
            batch_result,
            report_dir=args.report_dir,
            prefix=args.prefix,
        )
        print("")
        print("Archivos de reporte:")
        for path in batch_result.report_files:
            print(f"- {path}")
        print(f"- {combined_path}")
        has_errors = any(report.errors for report in batch_result.reports.values())
        return 0 if not has_errors else 1
    finally:
        db.close()
