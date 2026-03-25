from app.schemas.academic import (
    GradeCatalogCreate,
    ModalityCatalogCreate,
    SectionCatalogCreate,
    StudentCreate,
    StudentEnrollmentCreate,
    TeacherAssignmentCreate,
    TeacherCreate,
)
from app.schemas.auth import LoginInput
from app.schemas.phase3 import (
    AccessRecoveryRequest,
    AnnouncementCreate,
    GradeRecordCreate,
    GradeRecordUpdate,
    PasswordResetConfirm,
    ReportCardIssueCreate,
    SubjectCatalogCreate,
)
from app.schemas.school import SchoolCreate
from app.schemas.tutor import StudentTutorCreate
from app.schemas.user import UserCreate

__all__ = [
    "AccessRecoveryRequest",
    "AnnouncementCreate",
    "GradeCatalogCreate",
    "GradeRecordCreate",
    "GradeRecordUpdate",
    "LoginInput",
    "ModalityCatalogCreate",
    "PasswordResetConfirm",
    "ReportCardIssueCreate",
    "SchoolCreate",
    "SectionCatalogCreate",
    "StudentCreate",
    "StudentEnrollmentCreate",
    "StudentTutorCreate",
    "SubjectCatalogCreate",
    "TeacherAssignmentCreate",
    "TeacherCreate",
    "UserCreate",
]
