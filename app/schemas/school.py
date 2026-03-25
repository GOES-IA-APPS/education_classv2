from typing import Optional

from pydantic import BaseModel


class SchoolCreate(BaseModel):
    code: str
    name: str
    sector: Optional[str] = None
    zone: Optional[str] = None
    department_code: Optional[int] = None
    municipality_code: Optional[int] = None
