from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[Optional[str]] = mapped_column(Text)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    school_code: Mapped[Optional[str]] = mapped_column(ForeignKey("schools.code"), index=True)
    teacher_id_persona: Mapped[Optional[str]] = mapped_column(
        ForeignKey("teachers.id_persona"),
        index=True,
    )
    student_nie: Mapped[Optional[str]] = mapped_column(ForeignKey("students.nie"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    role: Mapped["Role"] = relationship(back_populates="users")
    school: Mapped[Optional["School"]] = relationship(back_populates="users")
    teacher: Mapped[Optional["Teacher"]] = relationship(back_populates="users")
    student: Mapped[Optional["Student"]] = relationship(back_populates="users")
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user")
    student_tutor_links: Mapped[list["UserStudentTutorLink"]] = relationship(back_populates="user")
    access_recovery_tokens: Mapped[list["AccessRecoveryToken"]] = relationship(back_populates="user")

    @property
    def role_code(self) -> Optional[str]:
        return self.role.code if self.role else None


class PasswordResetToken(TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")


class AcademicYearCatalog(TimestampMixin, Base):
    __tablename__ = "academic_year_catalogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    academic_year: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(80))
    source_type: Mapped[str] = mapped_column(String(20), default="derived")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GradeCatalog(TimestampMixin, Base):
    __tablename__ = "grade_catalogs"
    __table_args__ = (
        UniqueConstraint(
            "school_code",
            "academic_year",
            "grade_label",
            name="uq_grade_catalog_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_code: Mapped[Optional[str]] = mapped_column(ForeignKey("schools.code"), index=True)
    academic_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    grade_label: Mapped[str] = mapped_column(String(60), index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school: Mapped[Optional["School"]] = relationship(back_populates="grade_catalogs")


class SectionCatalog(TimestampMixin, Base):
    __tablename__ = "section_catalogs"
    __table_args__ = (
        UniqueConstraint(
            "school_code",
            "academic_year",
            "grade_label",
            "section_code",
            "section_name",
            name="uq_section_catalog_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_code: Mapped[Optional[str]] = mapped_column(ForeignKey("schools.code"), index=True)
    academic_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    grade_label: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    section_code: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    section_name: Mapped[Optional[str]] = mapped_column(String(30))
    shift: Mapped[Optional[str]] = mapped_column(String(30))
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school: Mapped[Optional["School"]] = relationship(back_populates="section_catalogs")


class ModalityCatalog(TimestampMixin, Base):
    __tablename__ = "modality_catalogs"
    __table_args__ = (
        UniqueConstraint(
            "school_code",
            "academic_year",
            "modality",
            "submodality",
            name="uq_modality_catalog_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_code: Mapped[Optional[str]] = mapped_column(ForeignKey("schools.code"), index=True)
    academic_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    modality: Mapped[str] = mapped_column(String(80), index=True)
    submodality: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school: Mapped[Optional["School"]] = relationship(back_populates="modality_catalogs")


class StudentTutor(TimestampMixin, Base):
    __tablename__ = "student_tutors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    dui: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    address: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    student_links: Mapped[list["StudentTutorStudentLink"]] = relationship(back_populates="student_tutor")
    user_links: Mapped[list["UserStudentTutorLink"]] = relationship(back_populates="student_tutor")


class StudentTutorStudentLink(TimestampMixin, Base):
    __tablename__ = "student_tutor_student_links"
    __table_args__ = (
        UniqueConstraint(
            "student_tutor_id",
            "student_nie",
            name="uq_student_tutor_student",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_tutor_id: Mapped[int] = mapped_column(ForeignKey("student_tutors.id"), index=True)
    student_nie: Mapped[str] = mapped_column(ForeignKey("students.nie"), index=True)
    relationship_label: Mapped[Optional[str]] = mapped_column(String(80))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    student_tutor: Mapped["StudentTutor"] = relationship(back_populates="student_links")
    student: Mapped["Student"] = relationship(back_populates="student_tutor_links")


class UserStudentTutorLink(TimestampMixin, Base):
    __tablename__ = "user_student_tutor_links"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "student_tutor_id",
            name="uq_user_student_tutor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    student_tutor_id: Mapped[int] = mapped_column(ForeignKey("student_tutors.id"), index=True)

    user: Mapped["User"] = relationship(back_populates="student_tutor_links")
    student_tutor: Mapped["StudentTutor"] = relationship(back_populates="user_links")


class SubjectCatalog(TimestampMixin, Base):
    __tablename__ = "subject_catalogs"
    __table_args__ = (
        UniqueConstraint(
            "school_code",
            "academic_year",
            "grade_label",
            "subject_code",
            name="uq_subject_catalog_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_code: Mapped[Optional[str]] = mapped_column(ForeignKey("schools.code"), index=True)
    academic_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    grade_label: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    subject_code: Mapped[str] = mapped_column(String(50), index=True)
    subject_name: Mapped[str] = mapped_column(String(120))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school: Mapped[Optional["School"]] = relationship(back_populates="subject_catalogs")
    grade_records: Mapped[list["GradeRecord"]] = relationship(back_populates="subject_catalog")
    report_card_items: Mapped[list["ReportCardItem"]] = relationship(back_populates="subject_catalog")


class GradeRecord(TimestampMixin, Base):
    __tablename__ = "grade_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_code: Mapped[str] = mapped_column(ForeignKey("schools.code"), index=True)
    student_nie: Mapped[str] = mapped_column(ForeignKey("students.nie"), index=True)
    teacher_id_persona: Mapped[Optional[str]] = mapped_column(
        ForeignKey("teachers.id_persona"),
        index=True,
    )
    teacher_assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teacher_assignments.id"),
        index=True,
    )
    subject_catalog_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subject_catalogs.id"),
        index=True,
    )
    academic_year: Mapped[int] = mapped_column(Integer, index=True)
    grade_label: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    section_code: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    section_id: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    subject_code: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    subject_name: Mapped[str] = mapped_column(String(120), index=True)
    evaluation_type: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    evaluation_name: Mapped[Optional[str]] = mapped_column(String(120))
    weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    score: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    observations: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)

    school: Mapped["School"] = relationship(back_populates="grade_records")
    student: Mapped["Student"] = relationship(back_populates="grade_records")
    teacher: Mapped[Optional["Teacher"]] = relationship(back_populates="grade_records")
    teacher_assignment: Mapped[Optional["TeacherAssignment"]] = relationship(back_populates="grade_records")
    subject_catalog: Mapped[Optional["SubjectCatalog"]] = relationship(back_populates="grade_records")
    created_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_user_id])
    updated_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[updated_by_user_id])


class ReportCard(TimestampMixin, Base):
    __tablename__ = "report_cards"
    __table_args__ = (
        UniqueConstraint(
            "school_code",
            "student_nie",
            "academic_year",
            "grade_label",
            "section_code",
            name="uq_report_card_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_code: Mapped[str] = mapped_column(ForeignKey("schools.code"), index=True)
    student_nie: Mapped[str] = mapped_column(ForeignKey("students.nie"), index=True)
    enrollment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("student_enrollments.id"),
        index=True,
    )
    academic_year: Mapped[int] = mapped_column(Integer, index=True)
    grade_label: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    section_code: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    responsible_teacher_id_persona: Mapped[Optional[str]] = mapped_column(
        ForeignKey("teachers.id_persona"),
        index=True,
    )
    responsible_director_id_persona: Mapped[Optional[str]] = mapped_column(
        ForeignKey("teachers.id_persona"),
        index=True,
    )
    overall_average: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    observations: Mapped[Optional[str]] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    issued_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="issued", index=True)

    school: Mapped["School"] = relationship(back_populates="report_cards")
    student: Mapped["Student"] = relationship(back_populates="report_cards")
    enrollment: Mapped[Optional["StudentEnrollment"]] = relationship(back_populates="report_cards")
    responsible_teacher: Mapped[Optional["Teacher"]] = relationship(
        foreign_keys=[responsible_teacher_id_persona],
        back_populates="report_cards_as_teacher",
    )
    responsible_director: Mapped[Optional["Teacher"]] = relationship(
        foreign_keys=[responsible_director_id_persona],
        back_populates="report_cards_as_director",
    )
    issued_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[issued_by_user_id])
    items: Mapped[list["ReportCardItem"]] = relationship(
        back_populates="report_card",
        cascade="all, delete-orphan",
    )


class ReportCardItem(TimestampMixin, Base):
    __tablename__ = "report_card_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_card_id: Mapped[int] = mapped_column(ForeignKey("report_cards.id"), index=True)
    subject_catalog_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subject_catalogs.id"),
        index=True,
    )
    subject_code: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    subject_name: Mapped[str] = mapped_column(String(120))
    evaluation_count: Mapped[int] = mapped_column(Integer, default=0)
    final_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    observations: Mapped[Optional[str]] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    report_card: Mapped["ReportCard"] = relationship(back_populates="items")
    subject_catalog: Mapped[Optional["SubjectCatalog"]] = relationship(back_populates="report_card_items")


class Announcement(TimestampMixin, Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_code: Mapped[Optional[str]] = mapped_column(ForeignKey("schools.code"), index=True)
    visible_to: Mapped[str] = mapped_column(String(40), default="all", index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    publication_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    event_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(30), default="published", index=True)

    school: Mapped[Optional["School"]] = relationship(back_populates="announcements")
    created_by_user: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])


class AccessRecoveryToken(TimestampMixin, Base):
    __tablename__ = "access_recovery_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="access_recovery_tokens")
