import re
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (
    Announcement,
    GradeRecord,
    ReportCard,
    ReportCardItem,
    School,
    Student,
    StudentEnrollment,
    StudentTutor,
    StudentTutorStudentLink,
    SubjectCatalog,
    Teacher,
    TeacherAssignment,
    User,
)
from app.schemas.user import UserCreate
from app.services.user_service import create_user


def login(client, email, password):
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


def admin_user(db_session):
    return db_session.scalar(select(User).where(User.email == "admin@example.org"))


def seed_phase3_fixture(db_session):
    school = School(
        code="SCH-P3",
        name="Centro Escolar Fase Tres",
        sector="PUBLICO",
        zone="URBANA",
        department_code=3,
        municipality_code=303,
    )
    teacher = Teacher(
        id=30,
        id_persona="DOC-P3",
        first_names="Sara Elena",
        last_names="Castro",
        gender="F",
        specialty="Ciencias",
    )
    director = Teacher(
        id=31,
        id_persona="DOC-DIR",
        first_names="Mario Jose",
        last_names="Rivas",
        gender="M",
        specialty="Direccion",
    )
    student = Student(
        id=40,
        nie="NIE-P3",
        first_name1="Lucia",
        last_name1="Ramirez",
        gender="F",
        age_current=13,
    )
    assignment = TeacherAssignment(
        id=50,
        id_persona="DOC-P3",
        school_code="SCH-P3",
        academic_year=2026,
        component_type="DOCENTE",
        grade_label="8",
        section_id="C",
        section_name="C",
        shift="MANANA",
    )
    director_assignment = TeacherAssignment(
        id=51,
        id_persona="DOC-DIR",
        school_code="SCH-P3",
        academic_year=2026,
        component_type="DIRECTOR",
        grade_label="8",
        section_id="C",
        section_name="C",
        shift="MANANA",
    )
    enrollment = StudentEnrollment(
        id=60,
        nie="NIE-P3",
        school_code="SCH-P3",
        academic_year=2026,
        section_code="C",
        grade_label="8",
        modality="PRESENCIAL",
        submodality="REGULAR",
    )
    tutor = StudentTutor(
        id=70,
        full_name="Claudia Ramirez",
        email="familia.p3@example.org",
        is_active=True,
    )
    tutor_link = StudentTutorStudentLink(
        id=71,
        student_tutor_id=70,
        student_nie="NIE-P3",
        relationship_label="Madre",
        is_primary=True,
    )
    db_session.add_all(
        [
            school,
            teacher,
            director,
            student,
            assignment,
            director_assignment,
            enrollment,
            tutor,
            tutor_link,
        ]
    )
    db_session.commit()


def test_admin_phase3_workflow_routes(client, db_session):
    seed_phase3_fixture(db_session)
    login(client, "admin@example.org", "Admin!234")

    assert client.post(
        "/catalogs/subjects",
        data={
            "school_code": "SCH-P3",
            "academic_year": "2026",
            "grade_label": "8",
            "subject_code": "SCI",
            "subject_name": "Ciencias",
            "display_order": "1",
        },
        follow_redirects=False,
    ).status_code == 303
    subject = db_session.scalar(select(SubjectCatalog).where(SubjectCatalog.subject_code == "SCI"))
    assert subject is not None

    assert client.post(
        "/grades",
        data={
            "school_code": "SCH-P3",
            "student_nie": "NIE-P3",
            "teacher_id_persona": "DOC-P3",
            "teacher_assignment_id": "50",
            "subject_catalog_id": str(subject.id),
            "academic_year": "2026",
            "grade_label": "8",
            "section_code": "C",
            "subject_code": "SCI",
            "subject_name": "Ciencias",
            "evaluation_type": "TRIMESTRE",
            "evaluation_name": "Primer trimestre",
            "weight": "40",
            "score": "87",
            "observations": "Buen desempeno",
        },
        follow_redirects=False,
    ).status_code == 303

    assert client.post(
        "/announcements",
        data={
            "school_code": "SCH-P3",
            "visible_to": "student_tutor",
            "title": "Reunion general",
            "content": "Se convoca a reunion con familias.",
            "event_date": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "status": "published",
        },
        follow_redirects=False,
    ).status_code == 303

    assert client.post(
        "/report-cards",
        data={
            "school_code": "SCH-P3",
            "student_nie": "NIE-P3",
            "enrollment_id": "60",
            "academic_year": "2026",
            "grade_label": "8",
            "section_code": "C",
            "responsible_teacher_id_persona": "DOC-P3",
            "responsible_director_id_persona": "DOC-DIR",
            "observations": "Buen cierre de periodo",
        },
        follow_redirects=False,
    ).status_code == 303

    grade = db_session.scalar(select(GradeRecord).where(GradeRecord.student_nie == "NIE-P3"))
    report_card = db_session.scalar(select(ReportCard).where(ReportCard.student_nie == "NIE-P3"))
    announcement = db_session.scalar(select(Announcement).where(Announcement.title == "Reunion general"))

    assert grade is not None
    assert report_card is not None
    assert announcement is not None
    assert report_card.items

    for path, expected_text in [
        ("/dashboard", "Boletas recientes"),
        ("/grades", "Ciencias"),
        ("/report-cards", "NIE-P3"),
        (f"/report-cards/{report_card.id}", "Buen cierre de periodo"),
        (f"/report-cards/{report_card.id}/print", "Documento"),
        ("/announcements", "Reunion general"),
        ("/reports", "Consolidado de notas"),
        ("/catalogs/subjects", "SCI"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert expected_text in response.text


def test_teacher_can_only_register_grades_for_real_assignment(client, db_session):
    seed_phase3_fixture(db_session)
    other_student = Student(id=41, nie="NIE-OUT", first_name1="Mario", last_name1="Fuera")
    other_enrollment = StudentEnrollment(
        id=61,
        nie="NIE-OUT",
        school_code="SCH-P3",
        academic_year=2026,
        section_code="Z",
        grade_label="9",
        modality="PRESENCIAL",
        submodality="REGULAR",
    )
    db_session.add_all([other_student, other_enrollment])
    db_session.commit()

    admin = admin_user(db_session)
    create_user(
        db_session,
        UserCreate(
            email="docente.p3@example.org",
            full_name="Docente F3",
            password="Teacher!234",
            role_code="teacher",
            school_code="SCH-P3",
            teacher_id_persona="DOC-P3",
        ),
        admin,
    )

    login(client, "docente.p3@example.org", "Teacher!234")

    success = client.post(
        "/grades",
        data={
            "school_code": "SCH-P3",
            "student_nie": "NIE-P3",
            "academic_year": "2026",
            "grade_label": "8",
            "section_code": "C",
            "subject_name": "Ciencias",
            "evaluation_type": "TRIMESTRE",
            "evaluation_name": "Segundo trimestre",
            "weight": "60",
            "score": "91",
        },
        follow_redirects=False,
    )
    assert success.status_code == 303

    failure = client.post(
        "/grades",
        data={
            "school_code": "SCH-P3",
            "student_nie": "NIE-OUT",
            "academic_year": "2026",
            "grade_label": "9",
            "section_code": "Z",
            "subject_name": "Ciencias",
            "evaluation_type": "TRIMESTRE",
            "evaluation_name": "Intento invalido",
            "weight": "20",
            "score": "70",
        },
    )
    assert failure.status_code == 400
    assert "compatible" in failure.text

    record = db_session.scalar(select(GradeRecord).where(GradeRecord.student_nie == "NIE-P3"))
    assert record is not None
    assert record.teacher_id_persona == "DOC-P3"


def test_student_tutor_portal_shows_linked_child_cards_and_announcements(client, db_session):
    seed_phase3_fixture(db_session)
    report_card = ReportCard(
        school_code="SCH-P3",
        student_nie="NIE-P3",
        enrollment_id=60,
        academic_year=2026,
        grade_label="8",
        section_code="C",
        responsible_teacher_id_persona="DOC-P3",
        responsible_director_id_persona="DOC-DIR",
        overall_average=89.5,
        status="issued",
    )
    report_card.items.append(
        ReportCardItem(
            subject_code="SCI",
            subject_name="Ciencias",
            evaluation_count=2,
            final_score=89.5,
        )
    )
    grade_record = GradeRecord(
        school_code="SCH-P3",
        student_nie="NIE-P3",
        teacher_id_persona="DOC-P3",
        teacher_assignment_id=50,
        academic_year=2026,
        grade_label="8",
        section_code="C",
        subject_code="SCI",
        subject_name="Ciencias",
        evaluation_type="TRIMESTRE",
        evaluation_name="Primer trimestre",
        weight=40,
        score=89.5,
    )
    announcement = Announcement(
        school_code="SCH-P3",
        visible_to="student_tutor",
        created_by_user_id=admin_user(db_session).id,
        title="Convocatoria familiar",
        content="Asistir a la reunion con familias.",
        publication_date=datetime.utcnow(),
        event_date=datetime.utcnow() + timedelta(days=1),
        status="published",
    )
    db_session.add_all([report_card, grade_record, announcement])
    db_session.commit()

    admin = admin_user(db_session)
    create_user(
        db_session,
        UserCreate(
            email="portal.familia@example.org",
            full_name="Familia P3",
            password="Tutor!234",
            role_code="student_tutor",
            student_tutor_id=70,
        ),
        admin,
    )

    login(client, "portal.familia@example.org", "Tutor!234")
    response = client.get("/parent-portal")

    assert response.status_code == 200
    assert "Lucia Ramirez" in response.text
    assert "Ciencias" in response.text
    assert "Convocatoria familiar" in response.text
    assert "89.5" in response.text


def test_access_recovery_flows_work(client):
    forgot_username = client.post("/access/forgot-username", data={"email": "admin@example.org"})
    assert forgot_username.status_code == 200
    username_link = re.search(r"/access/recover-username/[A-Za-z0-9_\\-]+", forgot_username.text)
    assert username_link

    recover_username = client.get(username_link.group(0))
    assert recover_username.status_code == 200
    assert "admin@example.org" in recover_username.text

    forgot_password = client.post("/access/forgot-password", data={"email": "admin@example.org"})
    assert forgot_password.status_code == 200
    password_link = re.search(r"/access/reset-password/[A-Za-z0-9_\\-]+", forgot_password.text)
    assert password_link

    reset_password = client.post(
        password_link.group(0),
        data={"password": "Admin!999"},
    )
    assert reset_password.status_code == 200
    assert "actualizada correctamente" in reset_password.text

    login(client, "admin@example.org", "Admin!999")
