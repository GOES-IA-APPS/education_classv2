from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Role, User
from app.auth.security import hash_password

ROLE_SEED_DATA = [
    ("admin", "Administrador", "Acceso total al sistema."),
    ("principal", "Director", "Gestiona la escuela que tiene asignada."),
    ("teacher", "Docente", "Consulta su escuela y su información asociada."),
    ("student", "Estudiante", "Consulta únicamente su expediente."),
    ("student_tutor", "Tutor", "Consulta la información de hijos vinculados."),
    ("administrative", "Administrativo", "Opera con permisos administrativos limitados."),
]


def seed_roles(db: Session) -> None:
    for code, name, description in ROLE_SEED_DATA:
        role = db.scalar(select(Role).where(Role.code == code))
        if not role:
            role = Role(code=code)
            db.add(role)
        role.name = name
        role.description = description
    db.flush()


def seed_admin(db: Session) -> None:
    admin_role = db.scalar(select(Role).where(Role.code == "admin"))
    if not admin_role:
        raise RuntimeError("El rol admin debe existir antes de sembrar el usuario administrador.")

    admin_user = db.scalar(select(User).where(User.email == settings.admin_email))
    if not admin_user:
        admin_user = User(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            full_name=settings.admin_full_name,
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin_user)
    else:
        admin_user.role_id = admin_role.id
        admin_user.full_name = admin_user.full_name or settings.admin_full_name
        admin_user.is_active = True


def initialize_phase1(db: Session) -> None:
    seed_roles(db)
    seed_admin(db)
    db.commit()
