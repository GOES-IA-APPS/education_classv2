from __future__ import annotations

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.models import GradeCatalog, ModalityCatalog, School, SectionCatalog
from app.schemas.academic import (
    GradeCatalogCreate,
    ModalityCatalogCreate,
    SectionCatalogCreate,
)


def list_grade_catalogs(db: Session, stmt) -> list[GradeCatalog]:
    return list(
        db.scalars(
            stmt.order_by(GradeCatalog.academic_year.desc(), GradeCatalog.grade_label)
        ).all()
    )


def catalog_tables(db: Session) -> set[str]:
    inspector = inspect(db.get_bind())
    return set(inspector.get_table_names())


def grade_catalogs_table_available(db: Session) -> bool:
    return "grade_catalogs" in catalog_tables(db)


def list_section_catalogs(db: Session, stmt) -> list[SectionCatalog]:
    return list(
        db.scalars(
            stmt.order_by(
                SectionCatalog.academic_year.desc(),
                SectionCatalog.grade_label,
                SectionCatalog.section_code,
                SectionCatalog.section_name,
            )
        ).all()
    )


def list_modality_catalogs(db: Session, stmt) -> list[ModalityCatalog]:
    return list(
        db.scalars(
            stmt.order_by(
                ModalityCatalog.academic_year.desc(),
                ModalityCatalog.modality,
                ModalityCatalog.submodality,
            )
        ).all()
    )


def save_grade_catalog(db: Session, payload: GradeCatalogCreate) -> GradeCatalog:
    if payload.school_code and not db.get(School, payload.school_code):
        raise ValueError("La escuela indicada no existe.")
    catalog = db.scalar(
        select(GradeCatalog).where(
            GradeCatalog.school_code == payload.school_code,
            GradeCatalog.academic_year == payload.academic_year,
            GradeCatalog.grade_label == payload.grade_label,
        )
    )
    if not catalog:
        catalog = GradeCatalog(
            school_code=payload.school_code,
            academic_year=payload.academic_year,
            grade_label=payload.grade_label,
        )
        db.add(catalog)
    catalog.display_name = payload.display_name
    catalog.source_type = "manual"
    catalog.is_active = True
    db.commit()
    db.refresh(catalog)
    return catalog


def get_grade_catalog_by_id(db: Session, stmt, grade_id: int) -> GradeCatalog | None:
    return db.scalar(stmt.where(GradeCatalog.id == grade_id))


def update_grade_catalog(db: Session, catalog: GradeCatalog, payload: GradeCatalogCreate) -> GradeCatalog:
    if payload.school_code and not db.get(School, payload.school_code):
        raise ValueError("La escuela indicada no existe.")

    duplicate = db.scalar(
        select(GradeCatalog).where(
            GradeCatalog.id != catalog.id,
            GradeCatalog.school_code == payload.school_code,
            GradeCatalog.academic_year == payload.academic_year,
            GradeCatalog.grade_label == payload.grade_label,
        )
    )
    if duplicate:
        raise ValueError("Ya existe un grado manual con la misma escuela, año y etiqueta.")

    catalog.school_code = payload.school_code
    catalog.academic_year = payload.academic_year
    catalog.grade_label = payload.grade_label
    catalog.display_name = payload.display_name
    catalog.source_type = "manual"
    catalog.is_active = True
    db.commit()
    db.refresh(catalog)
    return catalog


def delete_grade_catalog(db: Session, grade_id: int) -> None:
    db.execute(delete(GradeCatalog).where(GradeCatalog.id == grade_id))
    db.commit()


def save_section_catalog(db: Session, payload: SectionCatalogCreate) -> SectionCatalog:
    if payload.school_code and not db.get(School, payload.school_code):
        raise ValueError("La escuela indicada no existe.")
    catalog = db.scalar(
        select(SectionCatalog).where(
            SectionCatalog.school_code == payload.school_code,
            SectionCatalog.academic_year == payload.academic_year,
            SectionCatalog.grade_label == payload.grade_label,
            SectionCatalog.section_code == payload.section_code,
            SectionCatalog.section_name == payload.section_name,
        )
    )
    if not catalog:
        catalog = SectionCatalog(
            school_code=payload.school_code,
            academic_year=payload.academic_year,
            grade_label=payload.grade_label,
            section_code=payload.section_code,
            section_name=payload.section_name,
        )
        db.add(catalog)
    catalog.shift = payload.shift
    catalog.source_type = "manual"
    catalog.is_active = True
    db.commit()
    db.refresh(catalog)
    return catalog


def save_modality_catalog(db: Session, payload: ModalityCatalogCreate) -> ModalityCatalog:
    if payload.school_code and not db.get(School, payload.school_code):
        raise ValueError("La escuela indicada no existe.")
    catalog = db.scalar(
        select(ModalityCatalog).where(
            ModalityCatalog.school_code == payload.school_code,
            ModalityCatalog.academic_year == payload.academic_year,
            ModalityCatalog.modality == payload.modality,
            ModalityCatalog.submodality == payload.submodality,
        )
    )
    if not catalog:
        catalog = ModalityCatalog(
            school_code=payload.school_code,
            academic_year=payload.academic_year,
            modality=payload.modality,
            submodality=payload.submodality,
        )
        db.add(catalog)
    catalog.source_type = "manual"
    catalog.is_active = True
    db.commit()
    db.refresh(catalog)
    return catalog
