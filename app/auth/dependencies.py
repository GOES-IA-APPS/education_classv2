from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.session_user import SessionUser
from app.db import get_db
from app.repositories.users import get_user_by_id


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> SessionUser:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    user = get_user_by_id(db, int(user_id))
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def require_roles(*allowed_role_codes: str):
    def checker(user: SessionUser = Depends(get_current_user)) -> SessionUser:
        if user.role_code not in allowed_role_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado.",
            )
        return user

    return checker
