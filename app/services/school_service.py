from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import School, StudentEnrollment, TeacherAssignment, User
from app.schemas.school import SchoolCreate
from app.services.pagination_service import paginate_entities
from app.services.access_service import (
    visible_assignments_stmt,
    visible_enrollments_stmt,
    visible_schools_stmt,
)
from app.utils.cache import build_cache_key, get_cache, invalidate_namespace, set_cache
from app.utils.pagination import DEFAULT_PER_PAGE, PaginationResult


def visible_schools(db: Session, current_user: User) -> list[School]:
    stmt = visible_schools_stmt(db, current_user).order_by(School.name)
    cache_key = build_cache_key(
        "visible-schools",
        scope={
            "user_id": current_user.id,
            "role_code": current_user.role_code,
            "school_code": current_user.school_code,
            "teacher_id_persona": current_user.teacher_id_persona,
            "student_nie": current_user.student_nie,
        },
    )
    codes = get_cache(cache_key)
    if codes is None:
        codes = tuple(db.scalars(stmt.with_only_columns(School.code)).all())
        set_cache(cache_key, codes)
    if not codes:
        return []
    positions = {code: index for index, code in enumerate(codes)}
    schools = list(
        db.scalars(select(School).where(School.code.in_(codes)).order_by(School.name, School.code)).all()
    )
    return sorted(schools, key=lambda school: positions.get(school.code, len(positions)))


def paginated_visible_schools(
    db: Session,
    current_user: User,
    *,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> PaginationResult[School]:
    base_stmt = visible_schools_stmt(db, current_user)
    fetch_stmt = visible_schools_stmt(db, current_user)
    return paginate_entities(
        db,
        base_stmt=base_stmt,
        fetch_stmt=fetch_stmt,
        id_column=School.code,
        order_by=(School.name, School.code),
        page=page,
        per_page=per_page,
        cache_namespace="schools",
        cache_scope={
            "user_id": current_user.id,
            "role_code": current_user.role_code,
            "school_code": current_user.school_code,
            "teacher_id_persona": current_user.teacher_id_persona,
            "student_nie": current_user.student_nie,
        },
    )


def get_school_detail(db: Session, current_user: User, school_code: str) -> School | None:
    school = db.scalar(
        visible_schools_stmt(db, current_user).where(School.code == school_code)
    )
    if not school:
        return None
    return school


def school_snapshot(db: Session, current_user: User, school_code: str) -> dict | None:
    school = get_school_detail(db, current_user, school_code)
    if not school:
        return None
    assignments = db.scalars(
        visible_assignments_stmt(db, current_user)
        .where(TeacherAssignment.school_code == school_code)
        .order_by(TeacherAssignment.academic_year.desc())
        .limit(15)
    ).all()
    enrollments = db.scalars(
        visible_enrollments_stmt(db, current_user)
        .where(StudentEnrollment.school_code == school_code)
        .order_by(StudentEnrollment.academic_year.desc())
        .limit(15)
    ).all()
    return {"school": school, "assignments": assignments, "enrollments": enrollments}


def create_or_update_school(db: Session, payload: SchoolCreate) -> School:
    school = db.get(School, payload.code)
    if not school:
        school = School(code=payload.code, name=payload.name)
        db.add(school)
    school.name = payload.name
    school.sector = payload.sector
    school.zone = payload.zone
    school.department_code = payload.department_code
    school.municipality_code = payload.municipality_code
    db.commit()
    db.refresh(school)
    invalidate_namespace("schools")
    invalidate_namespace("visible-schools")
    return school
