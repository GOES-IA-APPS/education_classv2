from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class TeacherCreate(BaseModel):
    id_persona: str
    nip: Optional[str] = None
    dui: Optional[str] = None
    first_names: Optional[str] = None
    last_names: Optional[str] = None
    gender: Optional[str] = None
    specialty: Optional[str] = None


class StudentCreate(BaseModel):
    nie: str
    gender: Optional[str] = None
    first_name1: Optional[str] = None
    first_name2: Optional[str] = None
    first_name3: Optional[str] = None
    last_name1: Optional[str] = None
    last_name2: Optional[str] = None
    last_name3: Optional[str] = None
    birth_date: Optional[date] = None
    age_current: Optional[int] = None
    father_full_name: Optional[str] = None
    mother_full_name: Optional[str] = None
    address_full: Optional[str] = None


class TeacherAssignmentCreate(BaseModel):
    id_persona: str
    school_code: str
    academic_year: int
    component_type: Optional[str] = None
    grade_label: Optional[str] = None
    section_id: Optional[str] = None
    section_name: Optional[str] = None
    shift: Optional[str] = None
    cod_adscrito: Optional[str] = None


class StudentEnrollmentCreate(BaseModel):
    nie: str
    school_code: str
    academic_year: int
    section_code: Optional[str] = None
    grade_label: Optional[str] = None
    modality: Optional[str] = None
    submodality: Optional[str] = None


class GradeCatalogCreate(BaseModel):
    school_code: Optional[str] = None
    academic_year: Optional[int] = None
    grade_label: str
    display_name: Optional[str] = None


class SectionCatalogCreate(BaseModel):
    school_code: Optional[str] = None
    academic_year: Optional[int] = None
    grade_label: Optional[str] = None
    section_code: Optional[str] = None
    section_name: Optional[str] = None
    shift: Optional[str] = None


class ModalityCatalogCreate(BaseModel):
    school_code: Optional[str] = None
    academic_year: Optional[int] = None
    modality: str
    submodality: Optional[str] = None
