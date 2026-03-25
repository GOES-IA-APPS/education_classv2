from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Announcement, User
from app.repositories.announcements import (
    ANNOUNCEMENT_LIST_OPTIONS,
    get_announcement_by_id,
    list_announcements,
    save_announcement,
)
from app.schemas.phase3 import AnnouncementCreate
from app.services.access_service import resolved_school_codes, visible_announcements_stmt


def search_announcements(
    db: Session,
    current_user: User,
    *,
    school_code: str | None = None,
    status: str | None = None,
    visible_to: str | None = None,
    upcoming_only: bool = False,
) -> list[Announcement]:
    stmt = visible_announcements_stmt(db, current_user).options(*ANNOUNCEMENT_LIST_OPTIONS)
    if school_code:
        stmt = stmt.where(Announcement.school_code == school_code)
    if status:
        stmt = stmt.where(Announcement.status == status)
    if visible_to:
        stmt = stmt.where(Announcement.visible_to == visible_to)
    if upcoming_only:
        stmt = stmt.where(Announcement.event_date.is_not(None), Announcement.event_date >= datetime.utcnow())
    return list_announcements(db, stmt)


def get_announcement_detail(db: Session, current_user: User, announcement_id: int) -> Announcement | None:
    return db.scalar(
        visible_announcements_stmt(db, current_user)
        .options(*ANNOUNCEMENT_LIST_OPTIONS)
        .where(Announcement.id == announcement_id)
    )


def create_announcement_entry(db: Session, payload: AnnouncementCreate, current_user: User) -> Announcement:
    school_code = payload.school_code
    if current_user.role_code in {"principal", "administrative"}:
        school_codes = resolved_school_codes(db, current_user) or set()
        school_code = current_user.school_code or (sorted(school_codes)[0] if school_codes else school_code)
    prepared = payload.model_copy(
        update={
            "school_code": school_code,
            "publication_date": payload.publication_date or datetime.utcnow(),
        }
    )
    return save_announcement(db, prepared, current_user.id)
