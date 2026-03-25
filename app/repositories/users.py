from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.orm import Session

from app.core.session_user import SessionUser
from app.utils.cache import build_cache_key, get_cache, set_cache


def _user_schema_snapshot(db: Session) -> dict[str, object]:
    bind = db.get_bind()
    cache_key = build_cache_key(
        "user-schema",
        scope={"url": getattr(bind.url, "render_as_string", lambda **_: str(bind.url))(hide_password=True)},
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return cached
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    snapshot = {
        "tables": tables,
        "user_columns": {column["name"] for column in inspector.get_columns("users")} if "users" in tables else set(),
        "role_columns": {column["name"] for column in inspector.get_columns("roles")} if "roles" in tables else set(),
    }
    set_cache(cache_key, snapshot)
    return snapshot


def _select_expression(columns: set[str], name: str, *, fallback: str = "NULL") -> str:
    if name in columns:
        return f"users.{name}"
    return f"{fallback}"


def _role_code_expression(snapshot: dict[str, object]) -> str:
    user_columns = snapshot["user_columns"]
    role_columns = snapshot["role_columns"]
    tables = snapshot["tables"]
    if "role" in user_columns:
        return "LOWER(users.role)"
    if "role_code" in user_columns:
        return "users.role_code"
    if "role_id" in user_columns and "roles" in tables and "code" in role_columns:
        return "roles.code"
    return "NULL"


def _user_join_clause(snapshot: dict[str, object]) -> str:
    user_columns = snapshot["user_columns"]
    clauses: list[str] = []
    if "role_id" in user_columns and "roles" in snapshot["tables"]:
        clauses.append("LEFT JOIN roles ON roles.id = users.role_id")
    if "teacher_id" in user_columns and "teachers" in snapshot["tables"]:
        clauses.append("LEFT JOIN teachers ON teachers.id = users.teacher_id")
    if "student_id" in user_columns and "students" in snapshot["tables"]:
        clauses.append("LEFT JOIN students ON students.id = users.student_id")
    return (" " + " ".join(clauses)) if clauses else ""


def _teacher_id_persona_expression(snapshot: dict[str, object]) -> str:
    user_columns = snapshot["user_columns"]
    tables = snapshot["tables"]
    if "teacher_id_persona" in user_columns:
        return "users.teacher_id_persona"
    if "teacher_id" in user_columns and "teachers" in tables:
        return "teachers.id_persona"
    return "NULL"


def _student_nie_expression(snapshot: dict[str, object]) -> str:
    user_columns = snapshot["user_columns"]
    tables = snapshot["tables"]
    if "student_nie" in user_columns:
        return "users.student_nie"
    if "student_id" in user_columns and "students" in tables:
        return "students.nie"
    return "NULL"


def _row_to_session_user(row) -> SessionUser:
    mapping = row._mapping
    return SessionUser(
        id=int(mapping["id"]),
        email=mapping["email"] or "",
        password_hash=mapping["password_hash"] or "",
        full_name=mapping["full_name"] or "",
        role_code=mapping["role_code"],
        school_code=mapping["school_code"],
        teacher_id_persona=mapping["teacher_id_persona"],
        student_nie=mapping["student_nie"],
        is_active=bool(mapping["is_active"]) if mapping["is_active"] is not None else True,
        last_login_at=mapping["last_login_at"],
    )


def get_user_by_email(db: Session, email: str) -> SessionUser | None:
    snapshot = _user_schema_snapshot(db)
    if "users" not in snapshot["tables"]:
        return None
    user_columns = snapshot["user_columns"]
    query = text(
        f"""
        SELECT
          users.id AS id,
          users.email AS email,
          {_select_expression(user_columns, 'password_hash')} AS password_hash,
          {_select_expression(user_columns, 'full_name')} AS full_name,
          {_role_code_expression(snapshot)} AS role_code,
          {_select_expression(user_columns, 'school_code')} AS school_code,
          {_teacher_id_persona_expression(snapshot)} AS teacher_id_persona,
          {_student_nie_expression(snapshot)} AS student_nie,
          {_select_expression(user_columns, 'is_active', fallback='1')} AS is_active,
          {_select_expression(user_columns, 'last_login_at')} AS last_login_at
        FROM users
        {_user_join_clause(snapshot)}
        WHERE users.email = :email
        LIMIT 1
        """
    )
    row = db.execute(query, {"email": email}).first()
    return _row_to_session_user(row) if row else None


def get_user_by_id(db: Session, user_id: int) -> SessionUser | None:
    snapshot = _user_schema_snapshot(db)
    if "users" not in snapshot["tables"]:
        return None
    user_columns = snapshot["user_columns"]
    query = text(
        f"""
        SELECT
          users.id AS id,
          users.email AS email,
          {_select_expression(user_columns, 'password_hash')} AS password_hash,
          {_select_expression(user_columns, 'full_name')} AS full_name,
          {_role_code_expression(snapshot)} AS role_code,
          {_select_expression(user_columns, 'school_code')} AS school_code,
          {_teacher_id_persona_expression(snapshot)} AS teacher_id_persona,
          {_student_nie_expression(snapshot)} AS student_nie,
          {_select_expression(user_columns, 'is_active', fallback='1')} AS is_active,
          {_select_expression(user_columns, 'last_login_at')} AS last_login_at
        FROM users
        {_user_join_clause(snapshot)}
        WHERE users.id = :user_id
        LIMIT 1
        """
    )
    row = db.execute(query, {"user_id": user_id}).first()
    return _row_to_session_user(row) if row else None


def list_users(
    db: Session,
    *,
    school_codes: Optional[set[str]] = None,
) -> list[SessionUser]:
    snapshot = _user_schema_snapshot(db)
    if "users" not in snapshot["tables"]:
        return []
    user_columns = snapshot["user_columns"]
    order_column = "users.created_at DESC" if "created_at" in user_columns else "users.id DESC"
    filters = []
    params: dict[str, object] = {}
    if school_codes and "school_code" in user_columns:
        sorted_codes = sorted(school_codes)
        filters.append(
            "users.school_code IN (" + ", ".join(f":school_code_{index}" for index, _ in enumerate(sorted_codes)) + ")"
        )
        params.update({f"school_code_{index}": code for index, code in enumerate(sorted_codes)})
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    query = text(
        f"""
        SELECT
          users.id AS id,
          users.email AS email,
          {_select_expression(user_columns, 'password_hash')} AS password_hash,
          {_select_expression(user_columns, 'full_name')} AS full_name,
          {_role_code_expression(snapshot)} AS role_code,
          {_select_expression(user_columns, 'school_code')} AS school_code,
          {_teacher_id_persona_expression(snapshot)} AS teacher_id_persona,
          {_student_nie_expression(snapshot)} AS student_nie,
          {_select_expression(user_columns, 'is_active', fallback='1')} AS is_active,
          {_select_expression(user_columns, 'last_login_at')} AS last_login_at
        FROM users
        {_user_join_clause(snapshot)}
        {where_clause}
        ORDER BY {order_column}
        """
    )
    return [_row_to_session_user(row) for row in db.execute(query, params).all()]


def count_users(db: Session, *, school_codes: Optional[set[str]] = None) -> int:
    snapshot = _user_schema_snapshot(db)
    if "users" not in snapshot["tables"]:
        return 0
    user_columns = snapshot["user_columns"]
    filters = []
    params: dict[str, object] = {}
    if school_codes and "school_code" in user_columns:
        sorted_codes = sorted(school_codes)
        filters.append(
            "users.school_code IN (" + ", ".join(f":school_code_{index}" for index, _ in enumerate(sorted_codes)) + ")"
        )
        params.update({f"school_code_{index}": code for index, code in enumerate(sorted_codes)})
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    query = text(f"SELECT COUNT(*) AS total FROM users {where_clause}")
    return int(db.execute(query, params).scalar() or 0)


def touch_last_login(db: Session, user_id: int) -> None:
    snapshot = _user_schema_snapshot(db)
    if "last_login_at" not in snapshot["user_columns"]:
        return
    db.execute(
        text("UPDATE users SET last_login_at = :last_login_at WHERE id = :user_id"),
        {"last_login_at": datetime.utcnow(), "user_id": user_id},
    )
    db.commit()
