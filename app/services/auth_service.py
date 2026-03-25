from __future__ import annotations

import re
from datetime import datetime, timedelta
from secrets import token_urlsafe

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from app.core.session_user import SessionUser
from app.auth.security import verify_password
from app.models import PasswordResetToken, User
from app.repositories.users import get_user_by_email, touch_last_login

LOCAL_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    normalized_email = email.strip().lower()
    try:
        return validate_email(
            normalized_email,
            check_deliverability=False,
        ).normalized
    except EmailNotValidError as exc:
        # The legacy mirror uses internal domains such as @school.local and @edu.local.
        # Accept them with a basic syntax check to preserve compatibility.
        if LOCAL_EMAIL_PATTERN.match(normalized_email):
            return normalized_email
        raise ValueError(str(exc)) from exc


def authenticate_user(db: Session, email: str, password: str) -> SessionUser | None:
    normalized_email = normalize_email(email)
    user = get_user_by_email(db, normalized_email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    touch_last_login(db, user.id)
    user.last_login_at = datetime.utcnow()
    return user


def issue_password_reset_token(db: Session, user: User) -> PasswordResetToken:
    token = PasswordResetToken(
        user_id=user.id,
        token=token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(hours=2),
        is_used=False,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token
