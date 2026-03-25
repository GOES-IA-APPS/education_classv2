from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SessionUser:
    id: int
    email: str
    password_hash: str
    full_name: str
    role_code: Optional[str]
    school_code: Optional[str]
    teacher_id_persona: Optional[str]
    student_nie: Optional[str]
    is_active: bool
    last_login_at: Optional[datetime] = None
