from __future__ import annotations

from collections import defaultdict
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GradeRecord, ReportCard, StudentEnrollment, TeacherAssignment, User
from app.repositories.report_cards import (
    REPORT_CARD_LIST_OPTIONS,
    get_existing_report_card,
    list_report_cards,
    replace_report_card_items,
)
from app.schemas.phase3 import ReportCardIssueCreate
from app.services.access_service import (
    visible_director_assignments_stmt,
    visible_enrollments_stmt,
    visible_grade_records_stmt,
    visible_report_cards_stmt,
)


def _final_score_from_rows(rows: list[GradeRecord]) -> float:
    weighted_rows = [
        (float(row.score), float(row.weight))
        for row in rows
        if row.score is not None and row.weight
    ]
    if weighted_rows:
        total_weight = sum(weight for _, weight in weighted_rows)
        if total_weight:
            return round(sum(score * weight for score, weight in weighted_rows) / total_weight, 2)
    plain_scores = [float(row.score) for row in rows if row.score is not None]
    if not plain_scores:
        return 0.0
    return round(fmean(plain_scores), 2)


def search_report_cards(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
    student_nie: str | None = None,
) -> list[ReportCard]:
    stmt = visible_report_cards_stmt(db, current_user).options(*REPORT_CARD_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(ReportCard.school_code == school_code)
    if academic_year:
        stmt = stmt.where(ReportCard.academic_year == academic_year)
    if grade_label:
        stmt = stmt.where(ReportCard.grade_label == grade_label)
    if section_code:
        stmt = stmt.where(ReportCard.section_code == section_code)
    if student_nie:
        stmt = stmt.where(ReportCard.student_nie == student_nie)
    return list_report_cards(db, stmt)


def get_report_card_detail(db: Session, current_user: User, report_card_id: int) -> ReportCard | None:
    return db.scalar(
        visible_report_cards_stmt(db, current_user)
        .options(*REPORT_CARD_LIST_OPTIONS)
        .where(ReportCard.id == report_card_id)
    )


def issue_report_card(db: Session, payload: ReportCardIssueCreate, current_user: User) -> ReportCard:
    enrollment_stmt = visible_enrollments_stmt(db, current_user).where(
        StudentEnrollment.nie == payload.student_nie,
        StudentEnrollment.school_code == payload.school_code,
        StudentEnrollment.academic_year == payload.academic_year,
    )
    if payload.enrollment_id:
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.id == payload.enrollment_id)
    if payload.grade_label:
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.grade_label == payload.grade_label)
    if payload.section_code:
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.section_code == payload.section_code)
    enrollment = db.scalar(enrollment_stmt)
    if not enrollment:
        raise ValueError("No existe una matrícula visible compatible para emitir la boleta.")

    record_stmt = visible_grade_records_stmt(db, current_user).where(
        GradeRecord.student_nie == enrollment.nie,
        GradeRecord.school_code == enrollment.school_code,
        GradeRecord.academic_year == enrollment.academic_year,
    )
    if enrollment.grade_label:
        record_stmt = record_stmt.where(GradeRecord.grade_label == enrollment.grade_label)
    if enrollment.section_code:
        record_stmt = record_stmt.where(
            (GradeRecord.section_code == enrollment.section_code)
            | (GradeRecord.section_id == enrollment.section_code)
        )
    records = db.scalars(record_stmt).all()
    if not records:
        raise ValueError("No hay notas visibles para generar la boleta.")

    grouped: dict[tuple[int | None, str | None, str], list[GradeRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.subject_catalog_id, record.subject_code, record.subject_name)].append(record)

    items = []
    final_scores: list[float] = []
    for key, rows in grouped.items():
        final_score = _final_score_from_rows(rows)
        final_scores.append(final_score)
        observations = "; ".join(sorted({row.observations for row in rows if row.observations}))
        display_order = min(
            row.subject_catalog.display_order if row.subject_catalog else 999 for row in rows
        )
        items.append(
            {
                "subject_catalog_id": key[0],
                "subject_code": key[1],
                "subject_name": key[2],
                "evaluation_count": len(rows),
                "final_score": final_score,
                "observations": observations or None,
                "display_order": display_order,
            }
        )
    items.sort(key=lambda item: (item["display_order"], item["subject_name"]))
    overall_average = round(fmean(final_scores), 2) if final_scores else 0.0

    existing = get_existing_report_card(
        db,
        school_code=enrollment.school_code,
        student_nie=enrollment.nie,
        academic_year=enrollment.academic_year,
        grade_label=payload.grade_label or enrollment.grade_label,
        section_code=payload.section_code or enrollment.section_code,
    )
    if not existing:
        existing = ReportCard(
            school_code=enrollment.school_code,
            student_nie=enrollment.nie,
            enrollment_id=enrollment.id,
            academic_year=enrollment.academic_year,
            grade_label=payload.grade_label or enrollment.grade_label,
            section_code=payload.section_code or enrollment.section_code,
        )
        db.add(existing)

    if payload.responsible_director_id_persona:
        director_id_persona = payload.responsible_director_id_persona
    else:
        director_assignment = db.scalar(
            visible_director_assignments_stmt(db, current_user).where(
                TeacherAssignment.school_code == enrollment.school_code,
                TeacherAssignment.academic_year == enrollment.academic_year,
            )
        )
        director_id_persona = director_assignment.id_persona if director_assignment else None

    existing.enrollment_id = enrollment.id
    existing.responsible_teacher_id_persona = payload.responsible_teacher_id_persona
    existing.responsible_director_id_persona = director_id_persona
    existing.overall_average = overall_average
    existing.observations = payload.observations
    existing.issued_by_user_id = current_user.id
    existing.status = payload.status
    db.flush()
    replace_report_card_items(db, existing, items)
    db.commit()
    db.refresh(existing)
    return existing
