from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.session_user import SessionUser
from app.auth.security import validate_password_strength, hash_password
from app.models import Role, School, Student, StudentTutor, Teacher, User, UserStudentTutorLink
from app.repositories.users import count_users, get_user_by_email, list_users
from app.schemas.user import UserCreate
from app.services.auth_service import normalize_email
from app.services.access_service import resolved_school_codes


def visible_users(db: Session, current_user: SessionUser) -> list[SessionUser]:
    if current_user.role_code == "admin":
        return list_users(db)
    school_codes = resolved_school_codes(db, current_user)
    if current_user.role_code in {"principal", "administrative"} and school_codes:
        return list_users(db, school_codes=school_codes)
    return [current_user]


def create_user(
    db: Session,
    payload: UserCreate,
    current_user: User,
    *,
    auto_commit: bool = True,
) -> User:
    validate_password_strength(payload.password)
    normalized_email = normalize_email(payload.email)

    existing_user = get_user_by_email(db, normalized_email)
    if existing_user:
        raise ValueError("Ya existe un usuario con ese correo.")

    role = db.scalar(select(Role).where(Role.code == payload.role_code))
    if not role:
        raise ValueError("El rol indicado no existe.")

    if current_user.role_code != "admin" and payload.role_code == "admin":
        raise ValueError("Solo un admin puede crear otro admin.")

    school_code = payload.school_code
    if current_user.role_code in {"principal", "administrative"}:
        school_codes = resolved_school_codes(db, current_user) or set()
        school_code = current_user.school_code or (sorted(school_codes)[0] if school_codes else school_code)

    if school_code and not db.get(School, school_code):
        raise ValueError("La escuela indicada no existe.")

    if payload.teacher_id_persona:
        teacher = db.scalar(
            select(Teacher).where(Teacher.id_persona == payload.teacher_id_persona)
        )
        if not teacher:
            raise ValueError("El docente indicado no existe.")

    if payload.student_nie:
        student = db.scalar(select(Student).where(Student.nie == payload.student_nie))
        if not student:
            raise ValueError("El alumno indicado no existe.")

    if payload.student_tutor_id:
        tutor = db.get(StudentTutor, payload.student_tutor_id)
        if not tutor:
            raise ValueError("El tutor indicado no existe.")

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=role.id,
        school_code=school_code,
        teacher_id_persona=payload.teacher_id_persona,
        student_nie=payload.student_nie,
        is_active=True,
    )
    db.add(user)
    db.flush()
    if payload.student_tutor_id:
        db.add(
            UserStudentTutorLink(
                user_id=user.id,
                student_tutor_id=payload.student_tutor_id,
            )
        )
    if auto_commit:
        db.commit()
        db.refresh(user)
    return user
