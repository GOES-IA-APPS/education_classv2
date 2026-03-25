from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User
from app.services.announcement_service import search_announcements
from app.services.grade_record_service import search_grade_records
from app.services.report_card_service import search_report_cards
from app.services.student_service import search_students


def parent_portal_snapshot(db: Session, current_user: User) -> dict:
    children = search_students(db, current_user)
    child_nies = [child.nie for child in children]
    child_cards = []
    child_grades = []
    for nie in child_nies:
        child_cards.extend(search_report_cards(db, current_user, student_nie=nie))
        child_grades.extend(search_grade_records(db, current_user, student_nie=nie))
    announcements = search_announcements(db, current_user)
    meetings = search_announcements(db, current_user, upcoming_only=True)
    return {
        "children": children,
        "report_cards": child_cards[:20],
        "grade_records": child_grades[:30],
        "announcements": announcements[:12],
        "meetings": meetings[:12],
    }
