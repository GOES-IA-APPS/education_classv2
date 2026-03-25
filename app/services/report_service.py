from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import GradeRecord, ReportCard, StudentEnrollment, TeacherAssignment, User
from app.services.access_service import (
    visible_assignments_stmt,
    visible_enrollments_stmt,
    visible_grade_records_stmt,
    visible_report_cards_stmt,
)

REPORT_GROUP_LIMIT = 200
REPORT_SCHOOL_LIMIT = 100


def build_reports(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    academic_year: int | None = None,
    grade_label: str | None = None,
    section_code: str | None = None,
) -> dict[str, list[dict]]:
    teacher_stmt = visible_assignments_stmt(db, current_user)
    enrollment_stmt = visible_enrollments_stmt(db, current_user)
    grade_stmt = visible_grade_records_stmt(db, current_user)
    report_card_stmt = visible_report_cards_stmt(db, current_user)

    if school_code:
        teacher_stmt = teacher_stmt.where(TeacherAssignment.school_code == school_code)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.school_code == school_code)
        grade_stmt = grade_stmt.where(GradeRecord.school_code == school_code)
        report_card_stmt = report_card_stmt.where(ReportCard.school_code == school_code)
    if academic_year:
        teacher_stmt = teacher_stmt.where(TeacherAssignment.academic_year == academic_year)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.academic_year == academic_year)
        grade_stmt = grade_stmt.where(GradeRecord.academic_year == academic_year)
        report_card_stmt = report_card_stmt.where(ReportCard.academic_year == academic_year)
    if grade_label:
        teacher_stmt = teacher_stmt.where(TeacherAssignment.grade_label == grade_label)
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.grade_label == grade_label)
        grade_stmt = grade_stmt.where(GradeRecord.grade_label == grade_label)
        report_card_stmt = report_card_stmt.where(ReportCard.grade_label == grade_label)
    if section_code:
        teacher_stmt = teacher_stmt.where(
            (TeacherAssignment.section_id == section_code) | (TeacherAssignment.section_name == section_code)
        )
        enrollment_stmt = enrollment_stmt.where(StudentEnrollment.section_code == section_code)
        grade_stmt = grade_stmt.where(
            (GradeRecord.section_code == section_code) | (GradeRecord.section_id == section_code)
        )
        report_card_stmt = report_card_stmt.where(ReportCard.section_code == section_code)

    teachers_by_school = db.execute(
        teacher_stmt.with_only_columns(
            TeacherAssignment.school_code,
            func.count(func.distinct(TeacherAssignment.id_persona)),
        )
        .group_by(TeacherAssignment.school_code)
        .order_by(TeacherAssignment.school_code)
        .limit(REPORT_SCHOOL_LIMIT)
    )
    students_by_school = db.execute(
        enrollment_stmt.with_only_columns(
            StudentEnrollment.school_code,
            func.count(func.distinct(StudentEnrollment.nie)),
        )
        .group_by(StudentEnrollment.school_code)
        .order_by(StudentEnrollment.school_code)
        .limit(REPORT_SCHOOL_LIMIT)
    )
    enrollments_by_grade = db.execute(
        enrollment_stmt.with_only_columns(
            StudentEnrollment.school_code,
            StudentEnrollment.academic_year,
            StudentEnrollment.grade_label,
            StudentEnrollment.section_code,
            func.count(StudentEnrollment.id),
        )
        .group_by(
            StudentEnrollment.school_code,
            StudentEnrollment.academic_year,
            StudentEnrollment.grade_label,
            StudentEnrollment.section_code,
        )
        .order_by(StudentEnrollment.academic_year.desc(), StudentEnrollment.grade_label, StudentEnrollment.section_code)
        .limit(REPORT_GROUP_LIMIT)
    )
    grades_consolidated = db.execute(
        grade_stmt.with_only_columns(
            GradeRecord.school_code,
            GradeRecord.academic_year,
            GradeRecord.grade_label,
            GradeRecord.section_code,
            GradeRecord.subject_name,
            func.avg(GradeRecord.score),
            func.count(GradeRecord.id),
        )
        .group_by(
            GradeRecord.school_code,
            GradeRecord.academic_year,
            GradeRecord.grade_label,
            GradeRecord.section_code,
            GradeRecord.subject_name,
        )
        .order_by(GradeRecord.academic_year.desc(), GradeRecord.subject_name)
        .limit(REPORT_GROUP_LIMIT)
    )
    report_cards_by_year = db.execute(
        report_card_stmt.with_only_columns(
            ReportCard.school_code,
            ReportCard.academic_year,
            func.count(ReportCard.id),
            func.avg(ReportCard.overall_average),
        )
        .group_by(ReportCard.school_code, ReportCard.academic_year)
        .order_by(ReportCard.academic_year.desc(), ReportCard.school_code)
        .limit(REPORT_GROUP_LIMIT)
    )

    return {
        "teachers_by_school": [
            {"school_code": row[0], "total": row[1]}
            for row in teachers_by_school
        ],
        "students_by_school": [
            {"school_code": row[0], "total": row[1]}
            for row in students_by_school
        ],
        "enrollments_by_grade": [
            {
                "school_code": row[0],
                "academic_year": row[1],
                "grade_label": row[2],
                "section_code": row[3],
                "total": row[4],
            }
            for row in enrollments_by_grade
        ],
        "grades_consolidated": [
            {
                "school_code": row[0],
                "academic_year": row[1],
                "grade_label": row[2],
                "section_code": row[3],
                "subject_name": row[4],
                "average_score": round(float(row[5] or 0), 2),
                "total_records": row[6],
            }
            for row in grades_consolidated
        ],
        "report_cards_by_year": [
            {
                "school_code": row[0],
                "academic_year": row[1],
                "total": row[2],
                "average_overall": round(float(row[3] or 0), 2),
            }
            for row in report_cards_by_year
        ],
    }
