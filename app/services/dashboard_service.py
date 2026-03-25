from __future__ import annotations

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.session_user import SessionUser
from app.models import Announcement, GradeRecord, ReportCard, School, Student, StudentEnrollment, Teacher, TeacherAssignment
from app.repositories.users import count_users
from app.services.access_service import (
    resolved_school_codes,
    visible_announcements_stmt,
    visible_assignments_stmt,
    visible_director_assignments_stmt,
    visible_enrollments_stmt,
    visible_grade_records_stmt,
    visible_report_cards_stmt,
    visible_schools_stmt,
    visible_students_stmt,
    visible_teachers_stmt,
)
from app.utils.cache import build_cache_key, get_cache, set_cache


def _count_rows(db: Session, stmt) -> int:
    subquery = stmt.order_by(None).subquery()
    return db.scalar(select(func.count()).select_from(subquery)) or 0


def _table_exists(db: Session, table_name: str) -> bool:
    bind = db.get_bind()
    cache_key = build_cache_key(
        "dashboard-table-exists",
        scope={"table": table_name, "url": str(bind.url).replace(getattr(bind.url, "password", "") or "", "***")},
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return bool(cached)
    exists = table_name in set(inspect(bind).get_table_names())
    set_cache(cache_key, exists)
    return exists


def dashboard_stats(db: Session, current_user: SessionUser) -> dict[str, int]:
    schools = _count_rows(
        db,
        visible_schools_stmt(db, current_user).with_only_columns(School.code),
    )
    teachers = _count_rows(
        db,
        visible_teachers_stmt(db, current_user).with_only_columns(Teacher.id_persona),
    )
    students = _count_rows(
        db,
        visible_students_stmt(db, current_user).with_only_columns(Student.nie),
    )
    directors = _count_rows(
        db,
        visible_director_assignments_stmt(db, current_user).with_only_columns(TeacherAssignment.id),
    )
    assignments = _count_rows(
        db,
        visible_assignments_stmt(db, current_user).with_only_columns(TeacherAssignment.id),
    )
    enrollments = _count_rows(
        db,
        visible_enrollments_stmt(db, current_user).with_only_columns(StudentEnrollment.id),
    )
    grade_records = (
        _count_rows(
            db,
            visible_grade_records_stmt(db, current_user).with_only_columns(GradeRecord.id),
        )
        if _table_exists(db, "grade_records")
        else 0
    )
    report_cards = (
        _count_rows(
            db,
            visible_report_cards_stmt(db, current_user).with_only_columns(ReportCard.id),
        )
        if _table_exists(db, "report_cards")
        else 0
    )
    announcements = (
        _count_rows(
            db,
            visible_announcements_stmt(db, current_user).with_only_columns(Announcement.id),
        )
        if _table_exists(db, "announcements")
        else 0
    )

    school_codes = resolved_school_codes(db, current_user)
    if current_user.role_code == "admin":
        users = count_users(db)
    elif current_user.role_code in {"principal", "administrative"} and school_codes:
        users = count_users(db, school_codes=school_codes)
    else:
        users = 1

    return {
        "schools": schools,
        "users": users,
        "teachers": teachers,
        "students": students,
        "directors": directors,
        "assignments": assignments,
        "enrollments": enrollments,
        "grade_records": grade_records,
        "report_cards": report_cards,
        "announcements": announcements,
    }


def dashboard_breakdown(db: Session, current_user: SessionUser) -> dict[str, list[dict]]:
    teacher_stmt = (
        visible_assignments_stmt(db, current_user)
        .with_only_columns(
            TeacherAssignment.school_code,
            func.count(func.distinct(TeacherAssignment.id_persona)),
        )
        .group_by(TeacherAssignment.school_code)
        .order_by(func.count(func.distinct(TeacherAssignment.id_persona)).desc())
        .limit(10)
    )
    student_stmt = (
        visible_enrollments_stmt(db, current_user)
        .with_only_columns(
            StudentEnrollment.school_code,
            func.count(func.distinct(StudentEnrollment.nie)),
        )
        .group_by(StudentEnrollment.school_code)
        .order_by(func.count(func.distinct(StudentEnrollment.nie)).desc())
        .limit(10)
    )
    assignments_by_year_stmt = (
        visible_assignments_stmt(db, current_user)
        .with_only_columns(
            TeacherAssignment.academic_year,
            func.count(TeacherAssignment.id),
        )
        .group_by(TeacherAssignment.academic_year)
        .order_by(TeacherAssignment.academic_year.desc())
        .limit(10)
    )
    enrollments_by_grade_section_stmt = (
        visible_enrollments_stmt(db, current_user)
        .with_only_columns(
            StudentEnrollment.academic_year,
            StudentEnrollment.grade_label,
            StudentEnrollment.section_code,
            func.count(StudentEnrollment.id),
        )
        .group_by(
            StudentEnrollment.academic_year,
            StudentEnrollment.grade_label,
            StudentEnrollment.section_code,
        )
        .order_by(
            StudentEnrollment.academic_year.desc(),
            func.count(StudentEnrollment.id).desc(),
        )
        .limit(12)
    )
    report_cards_recent_stmt = None
    if _table_exists(db, "report_cards"):
        report_cards_recent_stmt = (
            visible_report_cards_stmt(db, current_user)
            .with_only_columns(
                ReportCard.id,
                ReportCard.school_code,
                ReportCard.student_nie,
                ReportCard.academic_year,
                ReportCard.overall_average,
                ReportCard.issued_at,
            )
            .order_by(ReportCard.issued_at.desc())
            .limit(10)
        )
    announcements_recent_stmt = None
    if _table_exists(db, "announcements"):
        announcements_recent_stmt = (
            visible_announcements_stmt(db, current_user)
            .with_only_columns(
                Announcement.id,
                Announcement.school_code,
                Announcement.title,
                Announcement.publication_date,
                Announcement.event_date,
            )
            .order_by(Announcement.publication_date.desc())
            .limit(10)
        )

    return {
        "teachers_by_school": [
            {"school_code": row[0], "total": row[1]}
            for row in db.execute(teacher_stmt)
            if row[0]
        ],
        "students_by_school": [
            {"school_code": row[0], "total": row[1]}
            for row in db.execute(student_stmt)
            if row[0]
        ],
        "assignments_by_year": [
            {"academic_year": row[0], "total": row[1]}
            for row in db.execute(assignments_by_year_stmt)
            if row[0] is not None
        ],
        "enrollments_by_grade_section": [
            {
                "academic_year": row[0],
                "grade_label": row[1],
                "section_code": row[2],
                "total": row[3],
            }
            for row in db.execute(enrollments_by_grade_section_stmt)
        ],
        "recent_report_cards": [
            {
                "id": row[0],
                "school_code": row[1],
                "student_nie": row[2],
                "academic_year": row[3],
                "overall_average": round(float(row[4] or 0), 2),
            }
            for row in (db.execute(report_cards_recent_stmt) if report_cards_recent_stmt is not None else [])
        ],
        "recent_announcements": [
            {
                "id": row[0],
                "school_code": row[1],
                "title": row[2],
                "publication_date": row[3],
                "event_date": row[4],
            }
            for row in (db.execute(announcements_recent_stmt) if announcements_recent_stmt is not None else [])
        ],
    }
