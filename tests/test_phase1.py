from passlib.hash import bcrypt
from sqlalchemy import func, select

from app.models import Role, School, User
from app.services.auth_service import normalize_email


def login_as_admin(client):
    response = client.post(
        "/login",
        data={"email": "admin@example.org", "password": "Admin!234"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_anonymous_dashboard_redirects_to_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_roles_and_admin_are_seeded(db_session):
    total_roles = db_session.scalar(select(func.count(Role.id)))
    admin_user = db_session.scalar(select(User).where(User.email == "admin@example.org"))

    assert total_roles == 6
    assert admin_user is not None
    assert admin_user.role is not None
    assert admin_user.role.code == "admin"


def test_login_and_dashboard_render(client):
    login_as_admin(client)
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Administrador General" in response.text
    assert "Escuelas" in response.text


def test_admin_can_create_school(client, db_session):
    login_as_admin(client)

    response = client.post(
        "/schools",
        data={
            "code": "SCH-001",
            "name": "Centro Escolar Prueba",
            "sector": "PUBLICO",
            "zone": "URBANA",
            "department_code": "1",
            "municipality_code": "101",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    school = db_session.get(School, "SCH-001")
    assert school is not None
    assert school.name == "Centro Escolar Prueba"


def test_admin_can_create_user(client, db_session):
    login_as_admin(client)
    client.post(
        "/schools",
        data={
            "code": "SCH-002",
            "name": "Centro Escolar Usuarios",
            "sector": "PUBLICO",
            "zone": "RURAL",
            "department_code": "2",
            "municipality_code": "202",
        },
    )

    response = client.post(
        "/users",
        data={
            "email": "principal.sch002@example.org",
            "full_name": "Directora Prueba",
            "password": "Principal!234",
            "role_code": "principal",
            "school_code": "SCH-002",
            "teacher_id_persona": "",
            "student_nie": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    user = db_session.scalar(
        select(User).where(User.email == "principal.sch002@example.org")
    )
    assert user is not None
    assert user.role is not None
    assert user.role.code == "principal"
    assert user.school_code == "SCH-002"


def test_normalize_email_accepts_internal_local_domains():
    assert normalize_email("Admin@School.Local") == "admin@school.local"


def test_login_accepts_legacy_bcrypt_hash_and_internal_domain(client, db_session):
    legacy_admin = db_session.scalar(select(User).where(User.email == "admin@example.org"))
    assert legacy_admin is not None
    legacy_admin.email = "admin@school.local"
    legacy_admin.password_hash = bcrypt.hash("Admin!234")
    db_session.commit()

    response = client.post(
        "/login",
        data={"email": "admin@school.local", "password": "Admin!234"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
