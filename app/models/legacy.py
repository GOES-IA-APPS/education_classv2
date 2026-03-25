from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class School(TimestampMixin, Base):
    __tablename__ = "schools"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[Optional[str]] = mapped_column(String(30))
    zone: Mapped[Optional[str]] = mapped_column(String(30))
    department_code: Mapped[Optional[int]] = mapped_column(SmallInteger)
    municipality_code: Mapped[Optional[int]] = mapped_column(Integer)

    teacher_assignments: Mapped[list["TeacherAssignment"]] = relationship(back_populates="school")
    student_enrollments: Mapped[list["StudentEnrollment"]] = relationship(back_populates="school")
    users: Mapped[list["User"]] = relationship(back_populates="school")
    grade_catalogs: Mapped[list["GradeCatalog"]] = relationship(back_populates="school")
    section_catalogs: Mapped[list["SectionCatalog"]] = relationship(back_populates="school")
    modality_catalogs: Mapped[list["ModalityCatalog"]] = relationship(back_populates="school")
    subject_catalogs: Mapped[list["SubjectCatalog"]] = relationship(back_populates="school")
    grade_records: Mapped[list["GradeRecord"]] = relationship(back_populates="school")
    report_cards: Mapped[list["ReportCard"]] = relationship(back_populates="school")
    announcements: Mapped[list["Announcement"]] = relationship(back_populates="school")


class Teacher(TimestampMixin, Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_persona: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nip: Mapped[Optional[str]] = mapped_column(String(30))
    dui: Mapped[Optional[str]] = mapped_column(String(30))
    first_names: Mapped[Optional[str]] = mapped_column(String(180))
    last_names: Mapped[Optional[str]] = mapped_column(String(180))
    gender: Mapped[Optional[str]] = mapped_column(String(15))
    specialty: Mapped[Optional[str]] = mapped_column(String(180))

    assignments: Mapped[list["TeacherAssignment"]] = relationship(back_populates="teacher")
    users: Mapped[list["User"]] = relationship(back_populates="teacher")
    grade_records: Mapped[list["GradeRecord"]] = relationship(back_populates="teacher")
    report_cards_as_teacher: Mapped[list["ReportCard"]] = relationship(
        foreign_keys="ReportCard.responsible_teacher_id_persona",
        back_populates="responsible_teacher",
    )
    report_cards_as_director: Mapped[list["ReportCard"]] = relationship(
        foreign_keys="ReportCard.responsible_director_id_persona",
        back_populates="responsible_director",
    )

    @property
    def full_name(self) -> str:
        return " ".join(part for part in [self.first_names, self.last_names] if part).strip()


class TeacherAssignment(TimestampMixin, Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint(
            "id_persona",
            "school_code",
            "academic_year",
            "section_id",
            name="uniq_teacher_school_year_section",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_persona: Mapped[str] = mapped_column(ForeignKey("teachers.id_persona"), index=True)
    school_code: Mapped[str] = mapped_column(ForeignKey("schools.code"), index=True)
    academic_year: Mapped[int] = mapped_column(SmallInteger, index=True)
    component_type: Mapped[Optional[str]] = mapped_column(String(512))
    grade_label: Mapped[Optional[str]] = mapped_column(String(60))
    section_id: Mapped[Optional[str]] = mapped_column(String(30))
    section_name: Mapped[Optional[str]] = mapped_column(String(30))
    shift: Mapped[Optional[str]] = mapped_column(String(30))
    cod_adscrito: Mapped[Optional[str]] = mapped_column(String(30))

    teacher: Mapped["Teacher"] = relationship(back_populates="assignments")
    school: Mapped["School"] = relationship(back_populates="teacher_assignments")
    grade_records: Mapped[list["GradeRecord"]] = relationship(back_populates="teacher_assignment")


class Student(TimestampMixin, Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nie: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    gender: Mapped[Optional[str]] = mapped_column(String(15))
    first_name1: Mapped[Optional[str]] = mapped_column(String(80))
    first_name2: Mapped[Optional[str]] = mapped_column(String(80))
    first_name3: Mapped[Optional[str]] = mapped_column(String(80))
    last_name1: Mapped[Optional[str]] = mapped_column(String(80))
    last_name2: Mapped[Optional[str]] = mapped_column(String(80))
    last_name3: Mapped[Optional[str]] = mapped_column(String(80))
    birth_date: Mapped[Optional[date]] = mapped_column(Date)
    age_current: Mapped[Optional[int]] = mapped_column(SmallInteger)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    father_full_name: Mapped[Optional[str]] = mapped_column(String(255))
    mother_full_name: Mapped[Optional[str]] = mapped_column(String(255))
    address_full: Mapped[Optional[str]] = mapped_column(String(500))

    student_enrollments: Mapped[list["StudentEnrollment"]] = relationship(back_populates="student")
    users: Mapped[list["User"]] = relationship(back_populates="student")
    student_tutor_links: Mapped[list["StudentTutorStudentLink"]] = relationship(back_populates="student")
    grade_records: Mapped[list["GradeRecord"]] = relationship(back_populates="student")
    report_cards: Mapped[list["ReportCard"]] = relationship(back_populates="student")

    @property
    def full_name(self) -> str:
        parts = [
            self.first_name1,
            self.first_name2,
            self.first_name3,
            self.last_name1,
            self.last_name2,
            self.last_name3,
        ]
        return " ".join(part for part in parts if part).strip()


class StudentEnrollment(TimestampMixin, Base):
    __tablename__ = "student_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "nie",
            "school_code",
            "academic_year",
            name="uniq_student_school_year",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nie: Mapped[str] = mapped_column(ForeignKey("students.nie"), index=True)
    school_code: Mapped[str] = mapped_column(ForeignKey("schools.code"), index=True)
    academic_year: Mapped[int] = mapped_column(SmallInteger, index=True)
    section_code: Mapped[Optional[str]] = mapped_column(String(30))
    grade_label: Mapped[Optional[str]] = mapped_column(String(60))
    modality: Mapped[Optional[str]] = mapped_column(String(80))
    submodality: Mapped[Optional[str]] = mapped_column(String(80))

    student: Mapped["Student"] = relationship(back_populates="student_enrollments")
    school: Mapped["School"] = relationship(back_populates="student_enrollments")
    report_cards: Mapped[list["ReportCard"]] = relationship(back_populates="enrollment")
