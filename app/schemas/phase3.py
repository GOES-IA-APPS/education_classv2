from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class SubjectCatalogCreate(BaseModel):
    school_code: Optional[str] = None
    academic_year: Optional[int] = None
    grade_label: Optional[str] = None
    subject_code: str
    subject_name: str
    display_order: int = 0


class GradeRecordCreate(BaseModel):
    school_code: str
    student_nie: str
    teacher_id_persona: Optional[str] = None
    teacher_assignment_id: Optional[int] = None
    subject_catalog_id: Optional[int] = None
    academic_year: int
    grade_label: Optional[str] = None
    section_code: Optional[str] = None
    section_id: Optional[str] = None
    subject_code: Optional[str] = None
    subject_name: str
    evaluation_type: Optional[str] = None
    evaluation_name: Optional[str] = None
    weight: Optional[float] = None
    score: Optional[float] = None
    observations: Optional[str] = None


class GradeRecordUpdate(BaseModel):
    subject_catalog_id: Optional[int] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    evaluation_type: Optional[str] = None
    evaluation_name: Optional[str] = None
    weight: Optional[float] = None
    score: Optional[float] = None
    observations: Optional[str] = None


class ReportCardIssueCreate(BaseModel):
    school_code: str
    student_nie: str
    enrollment_id: Optional[int] = None
    academic_year: int
    grade_label: Optional[str] = None
    section_code: Optional[str] = None
    responsible_teacher_id_persona: Optional[str] = None
    responsible_director_id_persona: Optional[str] = None
    observations: Optional[str] = None
    status: str = "issued"


class AnnouncementCreate(BaseModel):
    school_code: Optional[str] = None
    visible_to: str = "all"
    title: str
    content: str
    publication_date: Optional[datetime] = None
    event_date: Optional[datetime] = None
    status: str = "published"


class AccessRecoveryRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str
