from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ReportCard, ReportCardItem, SubjectCatalog, Teacher

REPORT_CARD_LIST_OPTIONS = (
    joinedload(ReportCard.school),
    joinedload(ReportCard.student),
    joinedload(ReportCard.enrollment),
    joinedload(ReportCard.responsible_teacher),
    joinedload(ReportCard.responsible_director),
    joinedload(ReportCard.items).joinedload(ReportCardItem.subject_catalog),
)


def report_card_list_stmt():
    return select(ReportCard).options(*REPORT_CARD_LIST_OPTIONS)


def get_report_card_by_id(db: Session, report_card_id: int) -> ReportCard | None:
    return db.scalar(report_card_list_stmt().where(ReportCard.id == report_card_id))


def list_report_cards(db: Session, stmt, limit: int = 200) -> list[ReportCard]:
    return list(
        db.scalars(
            stmt.order_by(
                ReportCard.issued_at.desc(),
                ReportCard.academic_year.desc(),
                ReportCard.school_code,
                ReportCard.student_nie,
            ).limit(limit)
        ).unique().all()
    )


def get_existing_report_card(
    db: Session,
    *,
    school_code: str,
    student_nie: str,
    academic_year: int,
    grade_label: str | None,
    section_code: str | None,
) -> ReportCard | None:
    return db.scalar(
        select(ReportCard).where(
            ReportCard.school_code == school_code,
            ReportCard.student_nie == student_nie,
            ReportCard.academic_year == academic_year,
            ReportCard.grade_label == grade_label,
            ReportCard.section_code == section_code,
        )
    )


def replace_report_card_items(
    db: Session,
    report_card: ReportCard,
    items: list[dict],
) -> ReportCard:
    report_card.items.clear()
    db.flush()
    for position, item in enumerate(items, start=1):
        report_card.items.append(
            ReportCardItem(
                subject_catalog_id=item.get("subject_catalog_id"),
                subject_code=item.get("subject_code"),
                subject_name=item["subject_name"],
                evaluation_count=item.get("evaluation_count", 0),
                final_score=item.get("final_score"),
                observations=item.get("observations"),
                display_order=item.get("display_order", position),
            )
        )
    db.flush()
    db.refresh(report_card)
    return report_card
