from __future__ import annotations

from datetime import datetime, timedelta
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, validate_password_strength
from app.models import AccessRecoveryToken, User
from app.repositories.users import get_user_by_email
from app.services.auth_service import normalize_email

USERNAME_REMINDER_PURPOSE = "username_reminder"
PASSWORD_RESET_PURPOSE = "password_reset"


def issue_access_recovery_token(
    db: Session,
    *,
    email: str,
    purpose: str,
) -> AccessRecoveryToken | None:
    normalized_email = normalize_email(email)
    user = get_user_by_email(db, normalized_email)
    if not user:
        return None
    token = AccessRecoveryToken(
        user_id=user.id,
        email=normalized_email,
        purpose=purpose,
        token=token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(hours=2),
        is_used=False,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def validate_access_recovery_token(
    db: Session,
    *,
    token: str,
    purpose: str,
) -> AccessRecoveryToken | None:
    recovery_token = db.scalar(
        select(AccessRecoveryToken).where(
            AccessRecoveryToken.token == token,
            AccessRecoveryToken.purpose == purpose,
        )
    )
    if not recovery_token or recovery_token.is_used or recovery_token.expires_at < datetime.utcnow():
        return None
    return recovery_token


def consume_username_recovery_token(db: Session, token: str) -> User | None:
    recovery_token = validate_access_recovery_token(
        db,
        token=token,
        purpose=USERNAME_REMINDER_PURPOSE,
    )
    if not recovery_token:
        return None
    recovery_token.is_used = True
    recovery_token.used_at = datetime.utcnow()
    db.commit()
    db.refresh(recovery_token)
    return recovery_token.user


def reset_password_with_token(db: Session, token: str, password: str) -> User | None:
    validate_password_strength(password)
    recovery_token = validate_access_recovery_token(
        db,
        token=token,
        purpose=PASSWORD_RESET_PURPOSE,
    )
    if not recovery_token:
        return None
    recovery_token.user.password_hash = hash_password(password)
    recovery_token.user.is_active = True
    recovery_token.is_used = True
    recovery_token.used_at = datetime.utcnow()
    db.commit()
    db.refresh(recovery_token.user)
    return recovery_token.user
