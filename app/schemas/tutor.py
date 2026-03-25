from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr


class StudentTutorCreate(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    dui: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    student_nie: Optional[str] = None
    relationship_label: Optional[str] = None
    is_primary: bool = False
    user_email: Optional[EmailStr] = None
    user_password: Optional[str] = None
    user_full_name: Optional[str] = None
