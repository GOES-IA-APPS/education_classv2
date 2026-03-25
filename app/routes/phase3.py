from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db import get_db
from app.models import User
from app.routes.web import clean_optional, parse_optional_int, redirect, render
from app.schemas.phase3 import (
    AccessRecoveryRequest,
    AnnouncementCreate,
    GradeRecordCreate,
    GradeRecordUpdate,
    ReportCardIssueCreate,
    SubjectCatalogCreate,
)
from app.services.announcement_service import (
    create_announcement_entry,
    get_announcement_detail,
    search_announcements,
)
from app.services.grade_record_service import (
    create_grade_record_entry,
    get_grade_record_detail,
    search_grade_records,
    update_grade_record_entry,
)
from app.services.parent_portal_service import parent_portal_snapshot
from app.services.recovery_service import (
    PASSWORD_RESET_PURPOSE,
    USERNAME_REMINDER_PURPOSE,
    consume_username_recovery_token,
    issue_access_recovery_token,
    reset_password_with_token,
    validate_access_recovery_token,
)
from app.services.report_card_service import (
    get_report_card_detail,
    issue_report_card,
    search_report_cards,
)
from app.services.report_service import build_reports
from app.services.school_service import visible_schools
from app.services.subject_service import create_subject_catalog_record, search_subject_catalogs

router = APIRouter()

GRADE_VIEW_ROLES = ("admin", "principal", "teacher", "student", "student_tutor", "administrative")
GRADE_EDIT_ROLES = ("admin", "principal", "teacher", "administrative")
REPORT_CARD_VIEW_ROLES = ("admin", "principal", "teacher", "student", "student_tutor", "administrative")
REPORT_CARD_ISSUE_ROLES = ("admin", "principal", "administrative")
ANNOUNCEMENT_MANAGE_ROLES = ("admin", "principal", "administrative")
REPORT_VIEW_ROLES = ("admin", "principal", "teacher", "administrative")


def parse_optional_float(value: Optional[str], label: str) -> Optional[float]:
    normalized = clean_optional(value)
    if normalized is None:
        return None
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} debe ser numérico.") from exc


def parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    normalized = clean_optional(value)
    if not normalized:
        return None
    return datetime.fromisoformat(normalized)


@router.get("/catalogs/subjects", response_class=HTMLResponse)
def subject_catalog_page(
    request: Request,
    school_code: Optional[str] = None,
    academic_year: Optional[str] = None,
    grade_label: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(require_roles("admin", "principal", "teacher", "administrative")),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "academic_year": parse_optional_int(academic_year, "Año académico"),
        "grade_label": clean_optional(grade_label),
        "q": clean_optional(q),
    }
    return render(
        request,
        "catalogs/subjects.html",
        {
            "subjects": search_subject_catalogs(db, current_user, **filters),
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/catalogs/subjects", response_class=HTMLResponse)
def create_subject_catalog_action(
    request: Request,
    school_code: str = Form(""),
    academic_year: str = Form(""),
    grade_label: str = Form(""),
    subject_code: str = Form(...),
    subject_name: str = Form(...),
    display_order: str = Form("0"),
    current_user: User = Depends(require_roles("admin", "principal", "administrative")),
    db: Session = Depends(get_db),
):
    try:
        create_subject_catalog_record(
            db,
            SubjectCatalogCreate(
                school_code=clean_optional(school_code),
                academic_year=parse_optional_int(academic_year, "Año académico"),
                grade_label=clean_optional(grade_label),
                subject_code=subject_code.strip(),
                subject_name=subject_name.strip(),
                display_order=parse_optional_int(display_order, "Orden") or 0,
            ),
        )
    except ValueError as exc:
        return render(
            request,
            "catalogs/subjects.html",
            {
                "subjects": search_subject_catalogs(db, current_user),
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/catalogs/subjects")


@router.get("/grades", response_class=HTMLResponse)
def grades_page(
    request: Request,
    school_code: Optional[str] = None,
    academic_year: Optional[str] = None,
    grade_label: Optional[str] = None,
    section_code: Optional[str] = None,
    student_nie: Optional[str] = None,
    teacher_id_persona: Optional[str] = None,
    subject_name: Optional[str] = None,
    current_user: User = Depends(require_roles(*GRADE_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "academic_year": parse_optional_int(academic_year, "Año académico"),
        "grade_label": clean_optional(grade_label),
        "section_code": clean_optional(section_code),
        "student_nie": clean_optional(student_nie),
        "teacher_id_persona": clean_optional(teacher_id_persona),
        "subject_name": clean_optional(subject_name),
    }
    return render(
        request,
        "grades/list.html",
        {
            "grade_records": search_grade_records(db, current_user, **filters),
            "subjects": search_subject_catalogs(db, current_user),
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/grades", response_class=HTMLResponse)
def create_grade_action(
    request: Request,
    school_code: str = Form(...),
    student_nie: str = Form(...),
    teacher_id_persona: str = Form(""),
    teacher_assignment_id: str = Form(""),
    subject_catalog_id: str = Form(""),
    academic_year: str = Form(...),
    grade_label: str = Form(""),
    section_code: str = Form(""),
    section_id: str = Form(""),
    subject_code: str = Form(""),
    subject_name: str = Form(""),
    evaluation_type: str = Form(""),
    evaluation_name: str = Form(""),
    weight: str = Form(""),
    score: str = Form(""),
    observations: str = Form(""),
    current_user: User = Depends(require_roles(*GRADE_EDIT_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_grade_record_entry(
            db,
            GradeRecordCreate(
                school_code=school_code.strip(),
                student_nie=student_nie.strip(),
                teacher_id_persona=clean_optional(teacher_id_persona),
                teacher_assignment_id=parse_optional_int(teacher_assignment_id, "Asignación docente"),
                subject_catalog_id=parse_optional_int(subject_catalog_id, "Materia"),
                academic_year=parse_optional_int(academic_year, "Año académico") or 0,
                grade_label=clean_optional(grade_label),
                section_code=clean_optional(section_code),
                section_id=clean_optional(section_id),
                subject_code=clean_optional(subject_code),
                subject_name=clean_optional(subject_name) or "",
                evaluation_type=clean_optional(evaluation_type),
                evaluation_name=clean_optional(evaluation_name),
                weight=parse_optional_float(weight, "Peso"),
                score=parse_optional_float(score, "Nota"),
                observations=clean_optional(observations),
            ),
            current_user,
        )
    except ValueError as exc:
        return render(
            request,
            "grades/list.html",
            {
                "grade_records": search_grade_records(db, current_user),
                "subjects": search_subject_catalogs(db, current_user),
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/grades")


@router.get("/grades/{grade_record_id}", response_class=HTMLResponse)
def grade_detail_page(
    request: Request,
    grade_record_id: int,
    current_user: User = Depends(require_roles(*GRADE_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    grade_record = get_grade_record_detail(db, current_user, grade_record_id)
    if not grade_record:
        raise HTTPException(status_code=404, detail="Nota no encontrada.")
    return render(
        request,
        "grades/detail.html",
        {
            "grade_record": grade_record,
            "subjects": search_subject_catalogs(db, current_user),
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/grades/{grade_record_id}", response_class=HTMLResponse)
def update_grade_action(
    request: Request,
    grade_record_id: int,
    subject_catalog_id: str = Form(""),
    subject_code: str = Form(""),
    subject_name: str = Form(""),
    evaluation_type: str = Form(""),
    evaluation_name: str = Form(""),
    weight: str = Form(""),
    score: str = Form(""),
    observations: str = Form(""),
    current_user: User = Depends(require_roles(*GRADE_EDIT_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        update_grade_record_entry(
            db,
            grade_record_id,
            GradeRecordUpdate(
                subject_catalog_id=parse_optional_int(subject_catalog_id, "Materia"),
                subject_code=clean_optional(subject_code),
                subject_name=clean_optional(subject_name),
                evaluation_type=clean_optional(evaluation_type),
                evaluation_name=clean_optional(evaluation_name),
                weight=parse_optional_float(weight, "Peso"),
                score=parse_optional_float(score, "Nota"),
                observations=clean_optional(observations),
            ),
            current_user,
        )
    except ValueError as exc:
        grade_record = get_grade_record_detail(db, current_user, grade_record_id)
        return render(
            request,
            "grades/detail.html",
            {
                "grade_record": grade_record,
                "subjects": search_subject_catalogs(db, current_user),
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect(f"/grades/{grade_record_id}")


@router.get("/report-cards", response_class=HTMLResponse)
def report_cards_page(
    request: Request,
    school_code: Optional[str] = None,
    academic_year: Optional[str] = None,
    grade_label: Optional[str] = None,
    section_code: Optional[str] = None,
    student_nie: Optional[str] = None,
    current_user: User = Depends(require_roles(*REPORT_CARD_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "academic_year": parse_optional_int(academic_year, "Año académico"),
        "grade_label": clean_optional(grade_label),
        "section_code": clean_optional(section_code),
        "student_nie": clean_optional(student_nie),
    }
    return render(
        request,
        "report_cards/list.html",
        {
            "report_cards": search_report_cards(db, current_user, **filters),
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/report-cards", response_class=HTMLResponse)
def issue_report_card_action(
    request: Request,
    school_code: str = Form(...),
    student_nie: str = Form(...),
    enrollment_id: str = Form(""),
    academic_year: str = Form(...),
    grade_label: str = Form(""),
    section_code: str = Form(""),
    responsible_teacher_id_persona: str = Form(""),
    responsible_director_id_persona: str = Form(""),
    observations: str = Form(""),
    current_user: User = Depends(require_roles(*REPORT_CARD_ISSUE_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        issue_report_card(
            db,
            ReportCardIssueCreate(
                school_code=school_code.strip(),
                student_nie=student_nie.strip(),
                enrollment_id=parse_optional_int(enrollment_id, "Matrícula"),
                academic_year=parse_optional_int(academic_year, "Año académico") or 0,
                grade_label=clean_optional(grade_label),
                section_code=clean_optional(section_code),
                responsible_teacher_id_persona=clean_optional(responsible_teacher_id_persona),
                responsible_director_id_persona=clean_optional(responsible_director_id_persona),
                observations=clean_optional(observations),
            ),
            current_user,
        )
    except ValueError as exc:
        return render(
            request,
            "report_cards/list.html",
            {
                "report_cards": search_report_cards(db, current_user),
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/report-cards")


@router.get("/report-cards/{report_card_id}", response_class=HTMLResponse)
def report_card_detail_page(
    request: Request,
    report_card_id: int,
    current_user: User = Depends(require_roles(*REPORT_CARD_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    report_card = get_report_card_detail(db, current_user, report_card_id)
    if not report_card:
        raise HTTPException(status_code=404, detail="Boleta no encontrada.")
    return render(
        request,
        "report_cards/detail.html",
        {"report_card": report_card},
        current_user=current_user,
    )


@router.get("/report-cards/{report_card_id}/print", response_class=HTMLResponse)
def report_card_print_page(
    request: Request,
    report_card_id: int,
    current_user: User = Depends(require_roles(*REPORT_CARD_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    report_card = get_report_card_detail(db, current_user, report_card_id)
    if not report_card:
        raise HTTPException(status_code=404, detail="Boleta no encontrada.")
    return render(
        request,
        "report_cards/print.html",
        {"report_card": report_card},
        current_user=current_user,
    )


@router.get("/announcements", response_class=HTMLResponse)
def announcements_page(
    request: Request,
    school_code: Optional[str] = None,
    status: Optional[str] = None,
    visible_to: Optional[str] = None,
    upcoming_only: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "status": clean_optional(status),
        "visible_to": clean_optional(visible_to),
        "upcoming_only": clean_optional(upcoming_only) in {"1", "on", "true", "yes", "si"},
    }
    return render(
        request,
        "announcements/list.html",
        {
            "announcements": search_announcements(db, current_user, **filters),
            "schools": visible_schools(db, current_user),
            "filters": filters,
            "error": None,
        },
        current_user=current_user,
    )


@router.post("/announcements", response_class=HTMLResponse)
def create_announcement_action(
    request: Request,
    school_code: str = Form(""),
    visible_to: str = Form("all"),
    title: str = Form(...),
    content: str = Form(...),
    publication_date: str = Form(""),
    event_date: str = Form(""),
    status: str = Form("published"),
    current_user: User = Depends(require_roles(*ANNOUNCEMENT_MANAGE_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        create_announcement_entry(
            db,
            AnnouncementCreate(
                school_code=clean_optional(school_code),
                visible_to=visible_to,
                title=title.strip(),
                content=content.strip(),
                publication_date=parse_optional_datetime(publication_date),
                event_date=parse_optional_datetime(event_date),
                status=status,
            ),
            current_user,
        )
    except ValueError as exc:
        return render(
            request,
            "announcements/list.html",
            {
                "announcements": search_announcements(db, current_user),
                "schools": visible_schools(db, current_user),
                "filters": {},
                "error": str(exc),
            },
            current_user=current_user,
            status_code=400,
        )
    return redirect("/announcements")


@router.get("/announcements/{announcement_id}", response_class=HTMLResponse)
def announcement_detail_page(
    request: Request,
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    announcement = get_announcement_detail(db, current_user, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado.")
    return render(
        request,
        "announcements/detail.html",
        {"announcement": announcement},
        current_user=current_user,
    )


@router.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    school_code: Optional[str] = None,
    academic_year: Optional[str] = None,
    grade_label: Optional[str] = None,
    section_code: Optional[str] = None,
    current_user: User = Depends(require_roles(*REPORT_VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    filters = {
        "school_code": clean_optional(school_code),
        "academic_year": parse_optional_int(academic_year, "Año académico"),
        "grade_label": clean_optional(grade_label),
        "section_code": clean_optional(section_code),
    }
    return render(
        request,
        "reports/index.html",
        {
            "reports": build_reports(db, current_user, **filters),
            "schools": visible_schools(db, current_user),
            "filters": filters,
        },
        current_user=current_user,
    )


@router.get("/parent-portal", response_class=HTMLResponse)
def parent_portal_page(
    request: Request,
    current_user: User = Depends(require_roles("student_tutor")),
    db: Session = Depends(get_db),
):
    return render(
        request,
        "parent_portal/index.html",
        parent_portal_snapshot(db, current_user),
        current_user=current_user,
    )


@router.get("/access/forgot-username", response_class=HTMLResponse)
def forgot_username_form(request: Request):
    return render(request, "auth/forgot_username.html", {"error": None, "result": None})


@router.post("/access/forgot-username", response_class=HTMLResponse)
def forgot_username_action(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        payload = AccessRecoveryRequest(email=email.strip())
    except (ValueError, ValidationError) as exc:
        return render(
            request,
            "auth/forgot_username.html",
            {"error": str(exc), "result": None},
            status_code=400,
        )
    token = issue_access_recovery_token(
        db,
        email=payload.email,
        purpose=USERNAME_REMINDER_PURPOSE,
    )
    result = {
        "message": "Si el correo existe, se generó un enlace seguro de recuperación.",
        "token": token.token if token else None,
        "link": f"/access/recover-username/{token.token}" if token else None,
    }
    return render(request, "auth/forgot_username.html", {"error": None, "result": result})


@router.get("/access/recover-username/{token}", response_class=HTMLResponse)
def recover_username_page(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    user = consume_username_recovery_token(db, token)
    if not user:
        return render(
            request,
            "auth/recover_username.html",
            {"error": "El token de recuperación no es válido o ya expiró.", "user": None},
            status_code=400,
        )
    return render(
        request,
        "auth/recover_username.html",
        {"error": None, "user": user},
    )


@router.get("/access/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return render(request, "auth/forgot_password.html", {"error": None, "result": None})


@router.post("/access/forgot-password", response_class=HTMLResponse)
def forgot_password_action(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        payload = AccessRecoveryRequest(email=email.strip())
    except (ValueError, ValidationError) as exc:
        return render(
            request,
            "auth/forgot_password.html",
            {"error": str(exc), "result": None},
            status_code=400,
        )
    token = issue_access_recovery_token(
        db,
        email=payload.email,
        purpose=PASSWORD_RESET_PURPOSE,
    )
    result = {
        "message": "Si el correo existe, se generó un enlace seguro para restablecer la contraseña.",
        "token": token.token if token else None,
        "link": f"/access/reset-password/{token.token}" if token else None,
    }
    return render(request, "auth/forgot_password.html", {"error": None, "result": result})


@router.get("/access/reset-password/{token}", response_class=HTMLResponse)
def reset_password_form(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    recovery_token = validate_access_recovery_token(db, token=token, purpose=PASSWORD_RESET_PURPOSE)
    if not recovery_token:
        return render(
            request,
            "auth/reset_password.html",
            {"error": "El token de recuperación no es válido o ya expiró.", "token": token, "success": None},
            status_code=400,
        )
    return render(
        request,
        "auth/reset_password.html",
        {"error": None, "token": token, "success": None},
    )


@router.post("/access/reset-password/{token}", response_class=HTMLResponse)
def reset_password_action(
    request: Request,
    token: str,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = reset_password_with_token(db, token, password)
    except ValueError as exc:
        return render(
            request,
            "auth/reset_password.html",
            {"error": str(exc), "token": token, "success": None},
            status_code=400,
        )
    if not user:
        return render(
            request,
            "auth/reset_password.html",
            {"error": "El token de recuperación no es válido o ya expiró.", "token": token, "success": None},
            status_code=400,
        )
    return render(
        request,
        "auth/reset_password.html",
        {"error": None, "token": token, "success": "La contraseña fue actualizada correctamente."},
    )
