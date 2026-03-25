from __future__ import annotations


def role_label(role_code: str | None) -> str:
    if not role_code:
        return "Sin rol"
    return role_code.replace("_", " ").title()
