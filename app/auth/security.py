from __future__ import annotations

import re

from passlib.exc import UnknownHashError
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,}$")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(plain_password, password_hash)
    except UnknownHashError:
        return False


def is_strong_password(password: str) -> bool:
    return bool(PASSWORD_PATTERN.match(password))


def validate_password_strength(password: str) -> None:
    if not is_strong_password(password):
        raise ValueError(
            "La contraseña debe tener al menos 8 caracteres, una mayúscula y un carácter especial."
        )
