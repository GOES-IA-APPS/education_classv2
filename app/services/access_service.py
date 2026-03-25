from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, and_, func, or_, select

from app.models import (
    Announcement,
    GradeCatalog,
    GradeRecord,
    ModalityCatalog,
    ReportCard,
    School,
    SectionCatalog,
    Student,
    StudentEnrollment,
    StudentTutor,
    StudentTutorStudentLink,
    SubjectCatalog,
    Teacher,
    TeacherAssignment,
    User,
    UserStudentTutorLink,
)

DIRECTOR_COMPONENT = "DIRECTOR"
ANNOUNCEMENT_AUDIENCE_BY_ROLE = {
    "teacher": {"all", "staff", "teacher"},
    "student": {"all", "student"},
    "student_tutor": {"all", "student_tutor"},
}


def normalize_component_type(value: Optional[str]) -> str:
    return (value or "").strip().upper()


def is_director_component(value: Optional[str]) -> bool:
    return normalize_component_type(value) == DIRECTOR_COMPONENT


def resolved_school_codes(db, current_user: User) -> Optional[set[str]]:
    if current_user.role_code == "admin":
        return None

    codes: set[str] = set()
    if current_user.school_code:
        codes.add(current_user.school_code)

    if current_user.role_code == "principal" and current_user.teacher_id_persona:
        principal_codes = db.scalars(
            select(TeacherAssignment.school_code).where(
                TeacherAssignment.id_persona == current_user.teacher_id_persona,
                func.upper(func.trim(func.coalesce(TeacherAssignment.component_type, "")))
                == DIRECTOR_COMPONENT,
            )
        ).all()
        codes.update(code for code in principal_codes if code)

    if current_user.role_code == "teacher" and current_user.teacher_id_persona:
        teacher_codes = db.scalars(
            select(TeacherAssignment.school_code).where(
                TeacherAssignment.id_persona == current_user.teacher_id_persona
            )
        ).all()
        codes.update(code for code in teacher_codes if code)

    if current_user.role_code == "student" and current_user.student_nie:
        student_codes = db.scalars(
            select(StudentEnrollment.school_code).where(StudentEnrollment.nie == current_user.student_nie)
        ).all()
        codes.update(code for code in student_codes if code)

    if current_user.role_code == "student_tutor":
        tutor_codes = db.scalars(
            select(StudentEnrollment.school_code)
            .join(StudentTutorStudentLink, StudentTutorStudentLink.student_nie == StudentEnrollment.nie)
            .join(
                UserStudentTutorLink,
                UserStudentTutorLink.student_tutor_id == StudentTutorStudentLink.student_tutor_id,
            )
            .where(UserStudentTutorLink.user_id == current_user.id)
        ).all()
        codes.update(code for code in tutor_codes if code)

    return codes


def apply_school_scope(stmt: Select, column, school_codes: Optional[set[str]]) -> Select:
    if school_codes is None:
        return stmt
    if not school_codes:
        return stmt.where(column == "__none__")
    return stmt.where(column.in_(sorted(school_codes)))


def teacher_student_match_clause():
    return and_(
        TeacherAssignment.school_code == StudentEnrollment.school_code,
        TeacherAssignment.academic_year == StudentEnrollment.academic_year,
        or_(
            TeacherAssignment.grade_label == StudentEnrollment.grade_label,
            TeacherAssignment.grade_label.is_(None),
            StudentEnrollment.grade_label.is_(None),
        ),
        or_(
            TeacherAssignment.section_id == StudentEnrollment.section_code,
            TeacherAssignment.section_name == StudentEnrollment.section_code,
            and_(
                TeacherAssignment.section_id.is_(None),
                TeacherAssignment.section_name.is_(None),
            ),
        ),
    )


def teacher_visible_students_stmt(current_user: User) -> Select:
    return (
        select(StudentEnrollment.nie)
        .join(TeacherAssignment, teacher_student_match_clause())
        .where(TeacherAssignment.id_persona == current_user.teacher_id_persona)
        .distinct()
    )


def visible_schools_stmt(db, current_user: User) -> Select:
    return apply_school_scope(select(School), School.code, resolved_school_codes(db, current_user))


def visible_teachers_stmt(db, current_user: User) -> Select:
    stmt = select(Teacher).distinct()
    if current_user.role_code == "admin":
        return stmt
    if current_user.role_code == "teacher" and current_user.teacher_id_persona:
        return stmt.where(Teacher.id_persona == current_user.teacher_id_persona)
    if current_user.role_code in {"principal", "administrative"}:
        return apply_school_scope(
            stmt.join(TeacherAssignment, Teacher.id_persona == TeacherAssignment.id_persona),
            TeacherAssignment.school_code,
            resolved_school_codes(db, current_user),
        )
    return stmt.where(Teacher.id == -1)


def visible_students_stmt(db, current_user: User) -> Select:
    stmt = select(Student).distinct()
    if current_user.role_code == "admin":
        return stmt
    if current_user.role_code in {"principal", "administrative"}:
        return apply_school_scope(
            stmt.join(StudentEnrollment, Student.nie == StudentEnrollment.nie),
            StudentEnrollment.school_code,
            resolved_school_codes(db, current_user),
        )
    if current_user.role_code == "teacher" and current_user.teacher_id_persona:
        return stmt.where(Student.nie.in_(teacher_visible_students_stmt(current_user)))
    if current_user.role_code == "student" and current_user.student_nie:
        return stmt.where(Student.nie == current_user.student_nie)
    if current_user.role_code == "student_tutor":
        return (
            stmt.join(StudentTutorStudentLink, Student.nie == StudentTutorStudentLink.student_nie)
            .join(
                UserStudentTutorLink,
                UserStudentTutorLink.student_tutor_id == StudentTutorStudentLink.student_tutor_id,
            )
            .where(UserStudentTutorLink.user_id == current_user.id)
        )
    return stmt.where(Student.id == -1)


def visible_assignments_stmt(db, current_user: User) -> Select:
    stmt = select(TeacherAssignment).distinct()
    if current_user.role_code == "admin":
        return stmt
    if current_user.role_code == "teacher" and current_user.teacher_id_persona:
        return stmt.where(TeacherAssignment.id_persona == current_user.teacher_id_persona)
    if current_user.role_code in {"principal", "administrative"}:
        return apply_school_scope(
            stmt,
            TeacherAssignment.school_code,
            resolved_school_codes(db, current_user),
        )
    return stmt.where(TeacherAssignment.id == -1)


def visible_director_assignments_stmt(db, current_user: User) -> Select:
    return visible_assignments_stmt(db, current_user).where(
        func.upper(func.trim(func.coalesce(TeacherAssignment.component_type, "")))
        == DIRECTOR_COMPONENT
    )


def visible_enrollments_stmt(db, current_user: User) -> Select:
    stmt = select(StudentEnrollment).distinct()
    if current_user.role_code == "admin":
        return stmt
    if current_user.role_code in {"principal", "administrative"}:
        return apply_school_scope(
            stmt,
            StudentEnrollment.school_code,
            resolved_school_codes(db, current_user),
        )
    if current_user.role_code == "teacher" and current_user.teacher_id_persona:
        return stmt.where(StudentEnrollment.nie.in_(teacher_visible_students_stmt(current_user)))
    if current_user.role_code == "student" and current_user.student_nie:
        return stmt.where(StudentEnrollment.nie == current_user.student_nie)
    if current_user.role_code == "student_tutor":
        return (
            stmt.join(StudentTutorStudentLink, StudentEnrollment.nie == StudentTutorStudentLink.student_nie)
            .join(
                UserStudentTutorLink,
                UserStudentTutorLink.student_tutor_id == StudentTutorStudentLink.student_tutor_id,
            )
            .where(UserStudentTutorLink.user_id == current_user.id)
        )
    return stmt.where(StudentEnrollment.id == -1)


def visible_tutors_stmt(db, current_user: User) -> Select:
    stmt = select(StudentTutor).distinct()
    if current_user.role_code == "admin":
        return stmt
    if current_user.role_code in {"principal", "administrative"}:
        return apply_school_scope(
            stmt.join(
                StudentTutorStudentLink,
                StudentTutor.id == StudentTutorStudentLink.student_tutor_id,
            ).join(StudentEnrollment, StudentTutorStudentLink.student_nie == StudentEnrollment.nie),
            StudentEnrollment.school_code,
            resolved_school_codes(db, current_user),
        )
    if current_user.role_code == "student_tutor":
        return (
            stmt.join(
                UserStudentTutorLink,
                StudentTutor.id == UserStudentTutorLink.student_tutor_id,
            )
            .where(UserStudentTutorLink.user_id == current_user.id)
        )
    return stmt.where(StudentTutor.id == -1)


def visible_grade_catalogs_stmt(db, current_user: User) -> Select:
    return apply_school_scope(
        select(GradeCatalog),
        GradeCatalog.school_code,
        resolved_school_codes(db, current_user),
    )


def visible_section_catalogs_stmt(db, current_user: User) -> Select:
    return apply_school_scope(
        select(SectionCatalog),
        SectionCatalog.school_code,
        resolved_school_codes(db, current_user),
    )


def visible_modality_catalogs_stmt(db, current_user: User) -> Select:
    return apply_school_scope(
        select(ModalityCatalog),
        ModalityCatalog.school_code,
        resolved_school_codes(db, current_user),
    )


def visible_subject_catalogs_stmt(db, current_user: User) -> Select:
    return apply_school_scope(
        select(SubjectCatalog),
        SubjectCatalog.school_code,
        resolved_school_codes(db, current_user),
    )


def visible_grade_records_stmt(db, current_user: User) -> Select:
    stmt = select(GradeRecord).distinct()
    if current_user.role_code == "admin":
        return stmt
    if current_user.role_code in {"principal", "administrative"}:
        return apply_school_scope(stmt, GradeRecord.school_code, resolved_school_codes(db, current_user))
    if current_user.role_code == "teacher" and current_user.teacher_id_persona:
        return stmt.where(
            or_(
                GradeRecord.teacher_id_persona == current_user.teacher_id_persona,
                GradeRecord.teacher_assignment_id.in_(
                    select(TeacherAssignment.id).where(
                        TeacherAssignment.id_persona == current_user.teacher_id_persona
                    )
                ),
            )
        )
    if current_user.role_code == "student" and current_user.student_nie:
        return stmt.where(GradeRecord.student_nie == current_user.student_nie)
    if current_user.role_code == "student_tutor":
        return (
            stmt.join(
                StudentTutorStudentLink,
                StudentTutorStudentLink.student_nie == GradeRecord.student_nie,
            )
            .join(
                UserStudentTutorLink,
                UserStudentTutorLink.student_tutor_id == StudentTutorStudentLink.student_tutor_id,
            )
            .where(UserStudentTutorLink.user_id == current_user.id)
        )
    return stmt.where(GradeRecord.id == -1)


def visible_report_cards_stmt(db, current_user: User) -> Select:
    stmt = select(ReportCard).distinct()
    if current_user.role_code == "admin":
        return stmt
    if current_user.role_code in {"principal", "administrative"}:
        return apply_school_scope(stmt, ReportCard.school_code, resolved_school_codes(db, current_user))
    if current_user.role_code == "teacher" and current_user.teacher_id_persona:
        return stmt.where(
            or_(
                ReportCard.responsible_teacher_id_persona == current_user.teacher_id_persona,
                ReportCard.student_nie.in_(teacher_visible_students_stmt(current_user)),
            )
        )
    if current_user.role_code == "student" and current_user.student_nie:
        return stmt.where(ReportCard.student_nie == current_user.student_nie)
    if current_user.role_code == "student_tutor":
        return (
            stmt.join(
                StudentTutorStudentLink,
                StudentTutorStudentLink.student_nie == ReportCard.student_nie,
            )
            .join(
                UserStudentTutorLink,
                UserStudentTutorLink.student_tutor_id == StudentTutorStudentLink.student_tutor_id,
            )
            .where(UserStudentTutorLink.user_id == current_user.id)
        )
    return stmt.where(ReportCard.id == -1)


def visible_announcements_stmt(db, current_user: User) -> Select:
    stmt = select(Announcement).distinct()
    if current_user.role_code == "admin":
        return stmt

    school_codes = resolved_school_codes(db, current_user)
    if school_codes:
        stmt = stmt.where(
            or_(
                Announcement.school_code.in_(sorted(school_codes)),
                Announcement.school_code.is_(None),
            )
        )
    elif school_codes == set():
        stmt = stmt.where(Announcement.id == -1)

    if current_user.role_code in {"principal", "administrative"}:
        return stmt

    allowed = ANNOUNCEMENT_AUDIENCE_BY_ROLE.get(current_user.role_code)
    if not allowed:
        return stmt.where(Announcement.id == -1)
    return stmt.where(
        Announcement.status == "published",
        Announcement.visible_to.in_(sorted(allowed)),
    )
