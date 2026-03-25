from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Announcement

ANNOUNCEMENT_LIST_OPTIONS = (
    joinedload(Announcement.school),
)


def announcement_list_stmt():
    return select(Announcement).options(*ANNOUNCEMENT_LIST_OPTIONS)


def get_announcement_by_id(db: Session, announcement_id: int) -> Announcement | None:
    return db.scalar(announcement_list_stmt().where(Announcement.id == announcement_id))


def list_announcements(db: Session, stmt, limit: int = 200) -> list[Announcement]:
    return list(
        db.scalars(
            stmt.order_by(
                Announcement.publication_date.desc(),
                Announcement.event_date.desc(),
            ).limit(limit)
        ).all()
    )


def save_announcement(db: Session, payload, created_by_user_id: int) -> Announcement:
    announcement = Announcement(
        school_code=payload.school_code,
        visible_to=payload.visible_to,
        created_by_user_id=created_by_user_id,
        title=payload.title,
        content=payload.content,
        publication_date=payload.publication_date,
        event_date=payload.event_date,
        status=payload.status,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement
