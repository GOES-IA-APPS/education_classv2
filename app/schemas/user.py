from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role_code: str
    school_code: Optional[str] = None
    teacher_id_persona: Optional[str] = None
    student_nie: Optional[str] = None
    student_tutor_id: Optional[int] = None
