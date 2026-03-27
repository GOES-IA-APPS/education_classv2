from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.auth.session import login_user, logout_user
from app.core.bootstrap import ROLE_SEED_DATA
from app.db import get_db
from app.models import User
from app.schemas.academic import (
    GradeCatalogCreate,
    ModalityCatalogCreate,
    SectionCatalogCreate,
    StudentCreate,
    StudentEnrollmentCreate,
    TeacherAssignmentCreate,
    TeacherCreate,
)
from app.schemas.school import SchoolCreate
from app.schemas.tutor import StudentTutorCreate
from app.schemas.user import UserCreate
from app.services.assignment_service import (
    create_assignment_record,
    get_assignment_detail,
    list_director_assignments,
    list_director_assignments_page,
    search_assignments,
    search_assignments_page,
)
from app.services.auth_service import authenticate_user
from app.services.catalog_service import (
    create_grade_catalog_record,
    create_modality_catalog_record,
    create_section_catalog_record,
    delete_grade_catalog_record,
    derive_grade_catalog_view,
    derive_modality_catalog_view,
    derive_section_catalog_view,
    get_grade_catalog_entry,
    list_manual_grade_catalogs,
    list_manual_modality_catalogs,
    list_manual_section_catalogs,
    search_grade_catalog_entries,
    update_grade_catalog_record,
)
from app.services.dashboard_service import dashboard_breakdown, dashboard_stats
from app.services.enrollment_service import (
    create_enrollment_record,
    get_enrollment_detail,
    search_enrollments,
    search_enrollments_page,
)
from app.services.school_service import (
    create_or_update_school,
    paginated_visible_schools,
    school_snapshot,
    visible_schools,
)
from app.services.student_service import (
    create_student_record,
    delete_student_record,
    get_student_detail,
    search_students,
    search_students_page,
    update_student_record,
)
from app.services.teacher_service import (
    create_teacher_record,
    get_teacher_detail,
    search_teachers,
    search_teachers_page,
)
from app.services.tutor_service import (
    create_tutor_record,
    get_tutor_detail,
    search_tutors,
)
from app.services.user_service import create_user, visible_users
from app.utils.formatters import role_label
from app.utils.pagination import DEFAULT_PER_PAGE, sanitize_page

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ACADEMIC_MANAGER_ROLES = ("admin", "principal", "administrative")
TEACHER_VIEW_ROLES = ("admin", "principal", "teacher", "administrative")
STUDENT_VIEW_ROLES = ("admin", "principal", "teacher", "student", "student_tutor", "administrative")
DIRECTOR_VIEW_ROLES = ("admin", "principal", "administrative")
TUTOR_VIEW_ROLES = ("admin", "principal", "student_tutor", "administrative")
CATALOG_VIEW_ROLES = ("admin", "principal", "teacher", "administrative")


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def render(
    request: Request,
    template_name: str,
    context: Optional[dict] = None,
    *,
    current_user: Optional[User] = None,
    status_code: int = 200,
):
    context = context or {}
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "request": request,
            "current_user": current_user,
            "role_label": role_label,
            **context,
        },
        status_code=status_code,
    )


def clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def parse_optional_int(value: Optional[str], label: str) -> Optional[int]:
    normalized = clean_optional(value)
    if normalized is None:
        return None
    try:
        return int(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} debe ser numérico.") from exc


def parse_checkbox(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "on", "true", "yes", "si"}


def build_url(path: str, **params: Optional[str]) -> str:
    clean_params = {key: value for key, value in params.items() if value not in (None, "")}
    if not clean_params:
        return path
    return f"{path}?{urlencode(clean_params)}"


def sanitize_students_return_to(value: Optional[str], *, fallback: str = "/students") -> str:
    normalized = clean_optional(value)
    if normalized and normalized.startswith("/students"):
        return normalized
    return fallback


def sanitize_catalog_grades_return_to(
    value: Optional[str],
    *,
    fallback: str = "/catalogs/grades",
) -> str:
    normalized = clean_optional(value)
    if normalized and normalized.startswith("/catalogs/grades"):
        return normalized
    return fallback


def available_role_codes_for(current_user: User) -> list[str]:
    return [
        code for code, _, _ in ROLE_SEED_DATA if current_user.role_code == "admin" or code != "admin"
    ]


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    if request.session.get("user_id"):
        return redirect("/dashboard")
    return redirect("/login")


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return render(request, "auth/login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = authenticate_user(db, email=email, password=password)
    except ValueError as exc:
        return render(
            request,
            "auth/login.html",
            {"error": str(exc)},
            status_code=400,
        )

    if not user:
        return render(
            request,
            "auth/login.html",
            {"error": "Credenciales inválidas."},
            status_code=400,
        )

    login_user(request, user.id)
    return redirect("/dashboard")


@router.post("/logout")
def logout_action(request: Request):
    logout_user(request)
    return redirect("/login")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return render(
        request,
        "dashboard.html",
        {
            "stats": dashboard_stats(db, current_user),
            "breakdown": dashboard_breakdown(db, current_user),
        },
        current_user=current_user,
    )


@router.get("/schools", response_class=HTMLResponse)
def schools_page(
    request: Request,
    q: Optional[str] = None,
    page: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = {"q": clean_optional(q)}
    pagination = paginated_visible_schools(
        db,
        current_user,
        q=filters["q"],
        page=sanitize_page(page),
        per_page=DEFAULT_PER_PAGE,
    )
    return render(
        request,
        "schools/list.html",
        {
            "schools": pagination.items,
            "pagination": pagination,
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/schools", response_class=HTMLResponse)
def create_school_action(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    sector: str = Form(""),
    zone: str = Form(""),
    department_code: str = Form(""),
    municipality_code: str = Form(""),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    try:
        payload = SchoolCreate(
            code=code.strip(),
            name=name.strip(),
            sector=clean_optional(sector),
            zone=clean_optional(zone),
            department_code=parse_optional_int(department_code, "Departamento"),
            municipality_code=parse_optional_int(municipality_code, "Municipio"),
        )
        create_or_update_school(db, payload)
    except ValueError as exc:
        pagination = paginated_visible_schools(
            db,
            current_user,
            q=None,
            page=1,
            per_page=DEFAULT_PER_PAGE,
        )
        return render(
            request,
            "schools/list.html",
            {
                "schools": pagination.items,
                "pagination": pagination,
                "filters": {"q": None},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/schools")


@router.get("/schools/{school_code}", response_class=HTMLResponse)
def school_detail_page(
    request: Request,
    school_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    snapshot = school_snapshot(db, current_user, school_code)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Escuela no encontrada.")
    return render(
        request,
        "schools/detail.html",
        snapshot,
        current_user=current_user,
    )


@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    current_user: User = Depends(require_roles("admin", "principal", "administrative")),
    db: Session = Depends(get_db),
):
    return render(
        request,
        "users/list.html",
        {
            "users": visible_users(db, current_user),
            "schools": visible_schools(db, current_user),
            "role_codes": available_role_codes_for(current_user),
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/users", response_class=HTMLResponse)
def create_user_action(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role_code: str = Form(...),
    school_code: str = Form(""),
    teacher_id_persona: str = Form(""),
    student_nie: str = Form(""),
    current_user: User = Depends(require_roles("admin", "principal", "administrative")),
    db: Session = Depends(get_db),
):
    try:
        payload = UserCreate(
            email=email.strip(),
            full_name=full_name.strip(),
            password=password,
            role_code=role_code,
            school_code=clean_optional(school_code),
            teacher_id_persona=clean_optional(teacher_id_persona),
            student_nie=clean_optional(student_nie),
        )
        create_user(db, payload, current_user)
    except ValueError as exc:
        return render(
            request,
            "users/list.html",
            {
                "users": visible_users(db, current_user),
                "schools": visible_schools(db, current_user),
                "role_codes": available_role_codes_for(current_user),
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    except HTTPException:
        raise

    return redirect("/users")


@router.get("/teachers", response_class=HTMLResponse)
def teachers_page(
    request: Request,
    school_code: Optional[str] = None,
    q: Optional[str] = None,
    page: Optional[str] = None,
    current_user: User = Depends(require_roles(*TEACHER_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "q": clean_optional(q),
    }
    pagination = search_teachers_page(
        db,
        current_user,
        page=sanitize_page(page),
        per_page=DEFAULT_PER_PAGE,
        **filters,
    )
    return render(
        request,
        "teachers/list.html",
        {
            "teachers": pagination.items,
            "pagination": pagination,
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/teachers", response_class=HTMLResponse)
def create_teacher_action(
    request: Request,
    id_persona: str = Form(...),
    nip: str = Form(""),
    dui: str = Form(""),
    first_names: str = Form(""),
    last_names: str = Form(""),
    gender: str = Form(""),
    specialty: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_teacher_record(
            db,
            TeacherCreate(
                id_persona=id_persona.strip(),
                nip=clean_optional(nip),
                dui=clean_optional(dui),
                first_names=clean_optional(first_names),
                last_names=clean_optional(last_names),
                gender=clean_optional(gender),
                specialty=clean_optional(specialty),
            ),
        )
    except ValueError as exc:
        pagination = search_teachers_page(
            db,
            current_user,
            page=1,
            per_page=DEFAULT_PER_PAGE,
        )
        return render(
            request,
            "teachers/list.html",
            {
                "teachers": pagination.items,
                "pagination": pagination,
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/teachers")


@router.get("/teachers/{id_persona}", response_class=HTMLResponse)
def teacher_detail_page(
    request: Request,
    id_persona: str,
    current_user: User = Depends(require_roles(*TEACHER_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    teacher = get_teacher_detail(db, current_user, id_persona)
    if not teacher:
        raise HTTPException(status_code=404, detail="Docente no encontrado.")
    return render(
        request,
        "teachers/detail.html",
        {"teacher": teacher},
        current_user=current_user,
    )


@router.get("/students", response_class=HTMLResponse)
def students_page(
    request: Request,
    school_code: Optional[str] = None,
    q: Optional[str] = None,
    page: Optional[str] = None,
    flash_type: Optional[str] = None,
    flash_message: Optional[str] = None,
    current_user: User = Depends(require_roles(*STUDENT_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "q": clean_optional(q),
    }
    try:
        pagination = search_students_page(
            db,
            current_user,
            page=sanitize_page(page),
            per_page=DEFAULT_PER_PAGE,
            **filters,
        )
        return render(
            request,
            "students/list.html",
            {
                "students": pagination.items,
                "pagination": pagination,
                "schools": visible_schools(db, current_user),
                "filters": filters,
                "error": None,
                "flash_type": clean_optional(flash_type),
                "flash_message": clean_optional(flash_message),
            },
            current_user=current_user,
        )
    except Exception as e:
        print("ERROR STUDENTS:", e)
        raise


@router.post("/students", response_class=HTMLResponse)
def create_student_action(
    request: Request,
    nie: str = Form(...),
    gender: str = Form(""),
    first_name1: str = Form(""),
    first_name2: str = Form(""),
    first_name3: str = Form(""),
    last_name1: str = Form(""),
    last_name2: str = Form(""),
    last_name3: str = Form(""),
    birth_date: str = Form(""),
    age_current: str = Form(""),
    father_full_name: str = Form(""),
    mother_full_name: str = Form(""),
    address_full: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_student_record(
            db,
            StudentCreate(
                nie=nie.strip(),
                gender=clean_optional(gender),
                first_name1=clean_optional(first_name1),
                first_name2=clean_optional(first_name2),
                first_name3=clean_optional(first_name3),
                last_name1=clean_optional(last_name1),
                last_name2=clean_optional(last_name2),
                last_name3=clean_optional(last_name3),
                birth_date=clean_optional(birth_date),
                age_current=parse_optional_int(age_current, "Edad actual"),
                father_full_name=clean_optional(father_full_name),
                mother_full_name=clean_optional(mother_full_name),
                address_full=clean_optional(address_full),
            ),
        )
    except ValueError as exc:
        pagination = search_students_page(
            db,
            current_user,
            page=1,
            per_page=DEFAULT_PER_PAGE,
        )
        return render(
            request,
            "students/list.html",
            {
                "students": pagination.items,
                "pagination": pagination,
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/students")


@router.post("/students/{nie}", response_class=HTMLResponse)
def update_student_action(
    request: Request,
    nie: str,
    gender: str = Form(""),
    first_name1: str = Form(""),
    first_name2: str = Form(""),
    first_name3: str = Form(""),
    last_name1: str = Form(""),
    last_name2: str = Form(""),
    last_name3: str = Form(""),
    birth_date: str = Form(""),
    age_current: str = Form(""),
    father_full_name: str = Form(""),
    mother_full_name: str = Form(""),
    address_full: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    current_student = get_student_detail(db, current_user, nie)
    if not current_student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado.")
    try:
        update_student_record(
            db,
            nie,
            StudentCreate(
                nie=nie,
                gender=clean_optional(gender),
                first_name1=clean_optional(first_name1),
                first_name2=clean_optional(first_name2),
                first_name3=clean_optional(first_name3),
                last_name1=clean_optional(last_name1),
                last_name2=clean_optional(last_name2),
                last_name3=clean_optional(last_name3),
                birth_date=clean_optional(birth_date),
                age_current=parse_optional_int(age_current, "Edad actual"),
                father_full_name=clean_optional(father_full_name),
                mother_full_name=clean_optional(mother_full_name),
                address_full=clean_optional(address_full),
            ),
        )
    except ValueError as exc:
        return render(
            request,
            "students/detail.html",
            {
                "student": current_student,
                "error": str(exc),
                "edit_mode": True,
                "can_manage_students": current_user.role_code in ACADEMIC_MANAGER_ROLES,
                "return_to": "/students",
                "flash_type": None,
                "flash_message": None,
            },
            current_user=current_user,
            status_code=400,
        )

    return redirect(
        build_url(
            f"/students/{nie}",
            flash_type="success",
            flash_message="Alumno actualizado correctamente.",
        )
    )


@router.get("/students/{nie}", response_class=HTMLResponse)
def student_detail_page(
    request: Request,
    nie: str,
    mode: Optional[str] = None,
    flash_type: Optional[str] = None,
    flash_message: Optional[str] = None,
    current_user: User = Depends(require_roles(*STUDENT_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        student = get_student_detail(db, current_user, nie)
        if not student:
            raise HTTPException(status_code=404, detail="Alumno no encontrado.")
        return render(
            request,
            "students/detail.html",
            {
                "student": student,
                "error": None,
                "edit_mode": mode == "edit" and current_user.role_code in ACADEMIC_MANAGER_ROLES,
                "can_manage_students": current_user.role_code in ACADEMIC_MANAGER_ROLES,
                "return_to": "/students",
                "flash_type": clean_optional(flash_type),
                "flash_message": clean_optional(flash_message),
            },
            current_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR STUDENT DETAIL:", e)
        raise


@router.post("/students/{nie}/delete")
def delete_student_action(
    nie: str,
    delete_confirmation: str = Form(""),
    next: str = Form("/students"),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    return_to = sanitize_students_return_to(next, fallback=f"/students/{nie}")
    if delete_confirmation != "DELETE":
        return redirect(
            build_url(
                return_to,
                flash_type="warning",
                flash_message="Debes escribir DELETE para confirmar la eliminación.",
            )
        )

    try:
        delete_student_record(db, current_user, nie)
    except ValueError as exc:
        return redirect(
            build_url(
                return_to,
                flash_type="error",
                flash_message=str(exc),
            )
        )

    return redirect(
        build_url(
            "/students",
            flash_type="success",
            flash_message="Eliminado con éxito.",
        )
    )


@router.get("/directors", response_class=HTMLResponse)
def directors_page(
    request: Request,
    school_code: Optional[str] = None,
    q: Optional[str] = None,
    page: Optional[str] = None,
    current_user: User = Depends(require_roles(*DIRECTOR_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "q": clean_optional(q),
    }
    pagination = list_director_assignments_page(
        db,
        current_user,
        page=sanitize_page(page),
        per_page=DEFAULT_PER_PAGE,
        **filters,
    )
    return render(
        request,
        "directors/list.html",
        {
            "director_assignments": pagination.items,
            "pagination": pagination,
            "schools": visible_schools(db, current_user),
            "filters": filters,
        },
        current_user=current_user,
    )


@router.get("/assignments", response_class=HTMLResponse)
def assignments_page(
    request: Request,
    school_code: Optional[str] = None,
    q: Optional[str] = None,
    page: Optional[str] = None,
    current_user: User = Depends(require_roles(*TEACHER_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "q": clean_optional(q),
    }
    pagination = search_assignments_page(
        db,
        current_user,
        page=sanitize_page(page),
        per_page=DEFAULT_PER_PAGE,
        **filters,
    )
    return render(
        request,
        "assignments/list.html",
        {
            "assignments": pagination.items,
            "pagination": pagination,
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/assignments", response_class=HTMLResponse)
def create_assignment_action(
    request: Request,
    id_persona: str = Form(...),
    school_code: str = Form(...),
    academic_year: str = Form(...),
    component_type: str = Form(""),
    grade_label: str = Form(""),
    section_id: str = Form(""),
    section_name: str = Form(""),
    shift: str = Form(""),
    cod_adscrito: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_assignment_record(
            db,
            TeacherAssignmentCreate(
                id_persona=id_persona.strip(),
                school_code=school_code.strip(),
                academic_year=parse_optional_int(academic_year, "Año académico") or 0,
                component_type=clean_optional(component_type),
                grade_label=clean_optional(grade_label),
                section_id=clean_optional(section_id),
                section_name=clean_optional(section_name),
                shift=clean_optional(shift),
                cod_adscrito=clean_optional(cod_adscrito),
            ),
        )
    except ValueError as exc:
        pagination = search_assignments_page(
            db,
            current_user,
            page=1,
            per_page=DEFAULT_PER_PAGE,
        )
        return render(
            request,
            "assignments/list.html",
            {
                "assignments": pagination.items,
                "pagination": pagination,
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/assignments")


@router.get("/assignments/{assignment_id}", response_class=HTMLResponse)
def assignment_detail_page(
    request: Request,
    assignment_id: int,
    current_user: User = Depends(require_roles(*TEACHER_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    assignment = get_assignment_detail(db, current_user, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignación no encontrada.")
    return render(
        request,
        "assignments/detail.html",
        {"assignment": assignment},
        current_user=current_user,
    )


@router.get("/enrollments", response_class=HTMLResponse)
def enrollments_page(
    request: Request,
    school_code: Optional[str] = None,
    q: Optional[str] = None,
    page: Optional[str] = None,
    current_user: User = Depends(require_roles(*STUDENT_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "q": clean_optional(q),
    }
    pagination = search_enrollments_page(
        db,
        current_user,
        page=sanitize_page(page),
        per_page=DEFAULT_PER_PAGE,
        **filters,
    )
    return render(
        request,
        "enrollments/list.html",
        {
            "enrollments": pagination.items,
            "pagination": pagination,
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/enrollments", response_class=HTMLResponse)
def create_enrollment_action(
    request: Request,
    nie: str = Form(...),
    school_code: str = Form(...),
    academic_year: str = Form(...),
    section_code: str = Form(""),
    grade_label: str = Form(""),
    modality: str = Form(""),
    submodality: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_enrollment_record(
            db,
            StudentEnrollmentCreate(
                nie=nie.strip(),
                school_code=school_code.strip(),
                academic_year=parse_optional_int(academic_year, "Año académico") or 0,
                section_code=clean_optional(section_code),
                grade_label=clean_optional(grade_label),
                modality=clean_optional(modality),
                submodality=clean_optional(submodality),
            ),
        )
    except ValueError as exc:
        pagination = search_enrollments_page(
            db,
            current_user,
            page=1,
            per_page=DEFAULT_PER_PAGE,
        )
        return render(
            request,
            "enrollments/list.html",
            {
                "enrollments": pagination.items,
                "pagination": pagination,
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/enrollments")


@router.get("/enrollments/{enrollment_id}", response_class=HTMLResponse)
def enrollment_detail_page(
    request: Request,
    enrollment_id: int,
    current_user: User = Depends(require_roles(*STUDENT_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    enrollment = get_enrollment_detail(db, current_user, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Matrícula no encontrada.")
    return render(
        request,
        "enrollments/detail.html",
        {"enrollment": enrollment},
        current_user=current_user,
    )


@router.get("/catalogs/grades", response_class=HTMLResponse)
def grade_catalog_page(
    request: Request,
    school_code: Optional[str] = None,
    q: Optional[str] = None,
    flash_type: Optional[str] = None,
    flash_message: Optional[str] = None,
    current_user: User = Depends(require_roles(*CATALOG_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {"school_code": clean_optional(school_code), "q": clean_optional(q)}
    try:
        grade_rows, compatibility_mode = search_grade_catalog_entries(db, current_user, **filters)
        return render(
            request,
            "catalogs/grades.html",
            {
                "grade_rows": grade_rows,
                "schools": visible_schools(db, current_user),
                "filters": filters,
                "error": None,
                "compatibility_mode": compatibility_mode,
                "flash_type": clean_optional(flash_type),
                "flash_message": clean_optional(flash_message),
            },
            current_user=current_user,
        )
    except Exception as e:
        print("ERROR GRADES:", e)
        raise


@router.post("/catalogs/grades", response_class=HTMLResponse)
def create_grade_catalog_action(
    request: Request,
    school_code: str = Form(""),
    academic_year: str = Form(""),
    grade_label: str = Form(...),
    display_name: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_grade_catalog_record(
            db,
            GradeCatalogCreate(
                school_code=clean_optional(school_code),
                academic_year=parse_optional_int(academic_year, "Año académico"),
                grade_label=grade_label.strip(),
                display_name=clean_optional(display_name),
            ),
        )
    except ValueError as exc:
        grade_rows, compatibility_mode = search_grade_catalog_entries(db, current_user)
        return render(
            request,
            "catalogs/grades.html",
            {
                "grade_rows": grade_rows,
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
                "compatibility_mode": compatibility_mode,
                "flash_type": None,
                "flash_message": None,
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/catalogs/grades")


@router.get("/catalogs/grades/detail", response_class=HTMLResponse)
def grade_catalog_detail_page(
    request: Request,
    source: str = "derived",
    grade_id: Optional[str] = None,
    school_code: Optional[str] = None,
    academic_year: Optional[str] = None,
    grade_label: Optional[str] = None,
    mode: Optional[str] = None,
    flash_type: Optional[str] = None,
    flash_message: Optional[str] = None,
    current_user: User = Depends(require_roles(*CATALOG_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        parsed_grade_id = parse_optional_int(grade_id, "ID del grado") if grade_id is not None else None
        parsed_year = parse_optional_int(academic_year, "Año académico")
        grade_entry = get_grade_catalog_entry(
            db,
            current_user,
            source_type=source,
            grade_id=parsed_grade_id,
            school_code=clean_optional(school_code),
            academic_year=parsed_year,
            grade_label=clean_optional(grade_label),
        )
        if not grade_entry:
            raise HTTPException(status_code=404, detail="Grado no encontrado.")
        related_sections = derive_section_catalog_view(
            db,
            current_user,
            school_code=grade_entry["school_code"],
            academic_year=grade_entry["academic_year"],
            grade_label=grade_entry["grade_label"],
        )
        return_to = build_url("/catalogs/grades", school_code=grade_entry["school_code"])
        return render(
            request,
            "catalogs/grade_detail.html",
            {
                "grade_entry": grade_entry,
                "related_sections": related_sections,
                "error": None,
                "edit_mode": mode == "edit" and current_user.role_code in ACADEMIC_MANAGER_ROLES,
                "can_manage_grades": current_user.role_code in ACADEMIC_MANAGER_ROLES,
                "return_to": return_to,
                "flash_type": clean_optional(flash_type),
                "flash_message": clean_optional(flash_message),
            },
            current_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR GRADES:", e)
        raise


@router.post("/catalogs/grades/{grade_id}/edit", response_class=HTMLResponse)
def update_grade_catalog_action(
    request: Request,
    grade_id: int,
    school_code: str = Form(""),
    academic_year: str = Form(""),
    grade_label: str = Form(...),
    display_name: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    grade_entry = get_grade_catalog_entry(db, current_user, source_type="manual", grade_id=grade_id)
    if not grade_entry:
        raise HTTPException(status_code=404, detail="Grado manual no encontrado.")

    try:
        update_grade_catalog_record(
            db,
            current_user,
            grade_id,
            GradeCatalogCreate(
                school_code=clean_optional(school_code),
                academic_year=parse_optional_int(academic_year, "Año académico"),
                grade_label=grade_label.strip(),
                display_name=clean_optional(display_name),
            ),
        )
    except ValueError as exc:
        return render(
            request,
            "catalogs/grade_detail.html",
            {
                "grade_entry": grade_entry,
                "related_sections": derive_section_catalog_view(
                    db,
                    current_user,
                    school_code=grade_entry["school_code"],
                    academic_year=grade_entry["academic_year"],
                    grade_label=grade_entry["grade_label"],
                ),
                "error": str(exc),
                "edit_mode": True,
                "can_manage_grades": True,
                "return_to": build_url("/catalogs/grades", school_code=grade_entry["school_code"]),
                "flash_type": None,
                "flash_message": None,
            },
            current_user=current_user,
            status_code=400,
        )

    return redirect(
        build_url(
            "/catalogs/grades/detail",
            source="manual",
            grade_id=str(grade_id),
            flash_type="success",
            flash_message="Grado actualizado correctamente.",
        )
    )


@router.post("/catalogs/grades/{grade_id}/delete")
def delete_grade_catalog_action(
    grade_id: int,
    delete_confirmation: str = Form(""),
    next: str = Form("/catalogs/grades"),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    return_to = sanitize_catalog_grades_return_to(next, fallback="/catalogs/grades")
    if delete_confirmation != "DELETE":
        return redirect(
            build_url(
                return_to,
                flash_type="warning",
                flash_message="Debes escribir DELETE para confirmar la eliminación.",
            )
        )
    try:
        delete_grade_catalog_record(db, current_user, grade_id)
    except ValueError as exc:
        return redirect(
            build_url(
                return_to,
                flash_type="error",
                flash_message=str(exc),
            )
        )
    return redirect(
        build_url(
            "/catalogs/grades",
            flash_type="success",
            flash_message="Eliminado con éxito.",
        )
    )


@router.post("/catalogs/grades/delete-derived")
def delete_derived_grade_catalog_action(
    school_code: str = Form(""),
    academic_year: str = Form(""),
    grade_label: str = Form(""),
    delete_confirmation: str = Form(""),
    next: str = Form("/catalogs/grades"),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
):
    return_to = sanitize_catalog_grades_return_to(
        next,
        fallback=build_url(
            "/catalogs/grades/detail",
            source="derived",
            school_code=clean_optional(school_code),
            academic_year=clean_optional(academic_year),
            grade_label=clean_optional(grade_label),
        ),
    )
    if delete_confirmation != "DELETE":
        return redirect(
            build_url(
                return_to,
                flash_type="warning",
                flash_message="Debes escribir DELETE para confirmar la eliminación.",
            )
        )
    return redirect(
        build_url(
            return_to,
            flash_type="error",
            flash_message="No se puede eliminar un grado derivado desde datos reales.",
        )
    )


@router.get("/catalogs/sections", response_class=HTMLResponse)
def section_catalog_page(
    request: Request,
    school_code: Optional[str] = None,
    academic_year: Optional[str] = None,
    grade_label: Optional[str] = None,
    current_user: User = Depends(require_roles(*CATALOG_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "academic_year": parse_optional_int(academic_year, "Año académico"),
        "grade_label": clean_optional(grade_label),
    }
    return render(
        request,
        "catalogs/sections.html",
        {
            "derived_sections": derive_section_catalog_view(db, current_user, **filters),
            "manual_sections": list_manual_section_catalogs(db, current_user),
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/catalogs/sections", response_class=HTMLResponse)
def create_section_catalog_action(
    request: Request,
    school_code: str = Form(""),
    academic_year: str = Form(""),
    grade_label: str = Form(""),
    section_code: str = Form(""),
    section_name: str = Form(""),
    shift: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_section_catalog_record(
            db,
            SectionCatalogCreate(
                school_code=clean_optional(school_code),
                academic_year=parse_optional_int(academic_year, "Año académico"),
                grade_label=clean_optional(grade_label),
                section_code=clean_optional(section_code),
                section_name=clean_optional(section_name),
                shift=clean_optional(shift),
            ),
        )
    except ValueError as exc:
        return render(
            request,
            "catalogs/sections.html",
            {
                "derived_sections": derive_section_catalog_view(db, current_user),
                "manual_sections": list_manual_section_catalogs(db, current_user),
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/catalogs/sections")


@router.get("/catalogs/modalities", response_class=HTMLResponse)
def modality_catalog_page(
    request: Request,
    school_code: Optional[str] = None,
    academic_year: Optional[str] = None,
    current_user: User = Depends(require_roles(*CATALOG_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "academic_year": parse_optional_int(academic_year, "Año académico"),
    }
    return render(
        request,
        "catalogs/modalities.html",
        {
            "derived_modalities": derive_modality_catalog_view(db, current_user, **filters),
            "manual_modalities": list_manual_modality_catalogs(db, current_user),
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/catalogs/modalities", response_class=HTMLResponse)
def create_modality_catalog_action(
    request: Request,
    school_code: str = Form(""),
    academic_year: str = Form(""),
    modality: str = Form(...),
    submodality: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_modality_catalog_record(
            db,
            ModalityCatalogCreate(
                school_code=clean_optional(school_code),
                academic_year=parse_optional_int(academic_year, "Año académico"),
                modality=modality.strip(),
                submodality=clean_optional(submodality),
            ),
        )
    except ValueError as exc:
        return render(
            request,
            "catalogs/modalities.html",
            {
                "derived_modalities": derive_modality_catalog_view(db, current_user),
                "manual_modalities": list_manual_modality_catalogs(db, current_user),
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/catalogs/modalities")


@router.get("/tutors", response_class=HTMLResponse)
def tutors_page(
    request: Request,
    student_nie: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(require_roles(*TUTOR_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "student_nie": clean_optional(student_nie),
        "q": clean_optional(q),
    }
    return render(
        request,
        "tutors/list.html",
        {
            "tutors": search_tutors(db, current_user, **filters),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/tutors", response_class=HTMLResponse)
def create_tutor_action(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    dui: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    student_nie: str = Form(""),
    relationship_label: str = Form(""),
    is_primary: str = Form(""),
    user_email: str = Form(""),
    user_password: str = Form(""),
    user_full_name: str = Form(""),
    current_user: User = Depends(require_roles(*ACADEMIC_MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_tutor_record(
            db,
            StudentTutorCreate(
                full_name=full_name.strip(),
                email=clean_optional(email),
                phone=clean_optional(phone),
                dui=clean_optional(dui),
                address=clean_optional(address),
                notes=clean_optional(notes),
                student_nie=clean_optional(student_nie),
                relationship_label=clean_optional(relationship_label),
                is_primary=parse_checkbox(is_primary),
                user_email=clean_optional(user_email),
                user_password=clean_optional(user_password),
                user_full_name=clean_optional(user_full_name),
            ),
            current_user,
        )
    except ValueError as exc:
        return render(
            request,
            "tutors/list.html",
            {
                "tutors": search_tutors(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/tutors")


@router.get("/tutors/{tutor_id}", response_class=HTMLResponse)
def tutor_detail_page(
    request: Request,
    tutor_id: int,
    current_user: User = Depends(require_roles(*TUTOR_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    tutor = get_tutor_detail(db, current_user, tutor_id)
    if not tutor:
        raise HTTPException(status_code=404, detail="Tutor no encontrado.")
    return render(
        request,
        "tutors/detail.html",
        {"tutor": tutor},
        current_user=current_user,
    )
