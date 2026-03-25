from sqlalchemy import select

from app.models import (
    Role,
    School,
    Student,
    StudentEnrollment,
    StudentTutor,
    StudentTutorStudentLink,
    Teacher,
    TeacherAssignment,
    User,
    UserStudentTutorLink,
)
from app.schemas.user import UserCreate
from app.services.catalog_service import derive_grade_catalog_view, derive_section_catalog_view
from app.services.report_service import build_reports
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


def seed_academic_fixture(db_session):
    school = School(
        code="SCH-A",
        name="Centro Escolar Alfa",
        sector="PUBLICO",
        zone="URBANA",
        department_code=1,
        municipality_code=101,
    )
    teacher_director = Teacher(
        id=1,
        id_persona="DOC-001",
        first_names="Maria Elena",
        last_names="Lopez Rivera",
        specialty="Direccion",
        gender="F",
    )
    teacher_other = Teacher(
        id=2,
        id_persona="DOC-002",
        first_names="Carlos Alberto",
        last_names="Martinez",
        specialty="Matematica",
        gender="M",
    )
    student_a = Student(
        id=1,
        nie="NIE-001",
        first_name1="Ana",
        last_name1="Garcia",
        gender="F",
        age_current=10,
        father_full_name="Padre Uno",
        mother_full_name="Madre Uno",
    )
    student_b = Student(
        id=2,
        nie="NIE-002",
        first_name1="Luis",
        last_name1="Perez",
        gender="M",
        age_current=11,
        father_full_name="Padre Dos",
        mother_full_name="Madre Dos",
    )
    assignment_director = TeacherAssignment(
        id=100,
        id_persona="DOC-001",
        school_code="SCH-A",
        academic_year=2026,
        component_type="DIRECTOR",
        grade_label="6",
        section_id="A",
        section_name="A",
        shift="MANANA",
        cod_adscrito="ADS-01",
    )
    assignment_teacher = TeacherAssignment(
        id=101,
        id_persona="DOC-002",
        school_code="SCH-A",
        academic_year=2026,
        component_type="DOCENTE",
        grade_label="5",
        section_id="B",
        section_name="B",
        shift="MANANA",
        cod_adscrito="ADS-02",
    )
    enrollment_a = StudentEnrollment(
        id=200,
        nie="NIE-001",
        school_code="SCH-A",
        academic_year=2026,
        section_code="A",
        grade_label="6",
        modality="PRESENCIAL",
        submodality="REGULAR",
    )
    enrollment_b = StudentEnrollment(
        id=201,
        nie="NIE-002",
        school_code="SCH-A",
        academic_year=2026,
        section_code="B",
        grade_label="5",
        modality="PRESENCIAL",
        submodality="REGULAR",
    )
    tutor = StudentTutor(
        id=300,
        full_name="Rosa Elena Garcia",
        email="tutor@example.org",
        phone="7777-1111",
        is_active=True,
    )
    tutor_link = StudentTutorStudentLink(
        id=301,
        student_tutor_id=300,
        student_nie="NIE-001",
        relationship_label="Madre",
        is_primary=True,
    )

    db_session.add_all(
        [
            school,
            teacher_director,
            teacher_other,
            student_a,
            student_b,
            assignment_director,
            assignment_teacher,
            enrollment_a,
            enrollment_b,
            tutor,
            tutor_link,
        ]
    )
    db_session.commit()


def test_admin_phase2_routes_and_forms_work(client, db_session):
    login(client, "admin@example.org", "Admin!234")

    assert client.post(
        "/schools",
        data={
            "code": "SCH-B",
            "name": "Centro Escolar Beta",
            "sector": "PUBLICO",
            "zone": "RURAL",
            "department_code": "2",
            "municipality_code": "202",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/teachers",
        data={
            "id_persona": "DOC-900",
            "nip": "NIP-900",
            "dui": "01234567-8",
            "first_names": "Julia",
            "last_names": "Morales",
            "gender": "F",
            "specialty": "Lenguaje",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/students",
        data={
            "nie": "NIE-900",
            "gender": "F",
            "first_name1": "Daniela",
            "last_name1": "Cruz",
            "age_current": "12",
            "father_full_name": "Padre Demo",
            "mother_full_name": "Madre Demo",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/assignments",
        data={
            "id_persona": "DOC-900",
            "school_code": "SCH-B",
            "academic_year": "2026",
            "component_type": "DIRECTOR",
            "grade_label": "9",
            "section_id": "A",
            "section_name": "A",
            "shift": "TARDE",
            "cod_adscrito": "ADS-B",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/enrollments",
        data={
            "nie": "NIE-900",
            "school_code": "SCH-B",
            "academic_year": "2026",
            "section_code": "A",
            "grade_label": "9",
            "modality": "PRESENCIAL",
            "submodality": "REGULAR",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/catalogs/grades",
        data={
            "school_code": "SCH-B",
            "academic_year": "2026",
            "grade_label": "9",
            "display_name": "Noveno Grado",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/catalogs/sections",
        data={
            "school_code": "SCH-B",
            "academic_year": "2026",
            "grade_label": "9",
            "section_code": "A",
            "section_name": "A",
            "shift": "TARDE",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/catalogs/modalities",
        data={
            "school_code": "SCH-B",
            "academic_year": "2026",
            "modality": "PRESENCIAL",
            "submodality": "REGULAR",
        },
        follow_redirects=False,
    ).status_code == 303
    assert client.post(
        "/tutors",
        data={
            "full_name": "Tutor Beta",
            "email": "tutor.beta@example.org",
            "student_nie": "NIE-900",
            "relationship_label": "Madre",
            "is_primary": "on",
            "user_email": "portal.beta@example.org",
            "user_password": "Tutor!234",
            "user_full_name": "Tutor Beta Usuario",
        },
        follow_redirects=False,
    ).status_code == 303

    teacher = db_session.scalar(select(Teacher).where(Teacher.id_persona == "DOC-900"))
    student = db_session.scalar(select(Student).where(Student.nie == "NIE-900"))
    school = db_session.get(School, "SCH-B")
    director_assignment = db_session.scalar(
        select(TeacherAssignment).where(TeacherAssignment.id_persona == "DOC-900")
    )
    tutor = db_session.scalar(select(StudentTutor).where(StudentTutor.full_name == "Tutor Beta"))

    assert school is not None
    assert teacher is not None
    assert student is not None
    assert director_assignment is not None
    assert tutor is not None

    for path, expected_text in [
        ("/teachers", "Julia Morales"),
        ("/students", "Daniela Cruz"),
        ("/assignments", "DOC-900"),
        ("/enrollments", "NIE-900"),
        ("/directors", "DOC-900"),
        ("/catalogs/grades", "Noveno Grado"),
        ("/catalogs/sections", "TARDE"),
        ("/catalogs/modalities", "PRESENCIAL"),
        ("/tutors", "Tutor Beta"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert expected_text in response.text


def test_teacher_scope_only_sees_own_assignment_and_students(client, db_session):
    seed_academic_fixture(db_session)
    admin = admin_user(db_session)
    create_user(
        db_session,
        UserCreate(
            email="docente@example.org",
            full_name="Docente Dos",
            password="Teacher!234",
            role_code="teacher",
            school_code="SCH-A",
            teacher_id_persona="DOC-002",
        ),
        admin,
    )

    login(client, "docente@example.org", "Teacher!234")

    teacher_page = client.get("/teachers")
    assignments_page = client.get("/assignments")
    students_page = client.get("/students")

    assert teacher_page.status_code == 200
    assert "Carlos Alberto Martinez" in teacher_page.text
    assert "Maria Elena Lopez Rivera" not in teacher_page.text

    assert assignments_page.status_code == 200
    assert "DOC-002" in assignments_page.text
    assert "DOC-001" not in assignments_page.text

    assert students_page.status_code == 200
    assert "NIE-002" in students_page.text
    assert "NIE-001" not in students_page.text


def test_principal_scope_can_be_derived_from_director_assignment(client, db_session):
    seed_academic_fixture(db_session)
    admin = admin_user(db_session)
    create_user(
        db_session,
        UserCreate(
            email="principal@example.org",
            full_name="Principal Alfa",
            password="Principal!234",
            role_code="principal",
            teacher_id_persona="DOC-001",
        ),
        admin,
    )

    login(client, "principal@example.org", "Principal!234")

    schools_page = client.get("/schools")
    directors_page = client.get("/directors")
    students_page = client.get("/students")

    assert schools_page.status_code == 200
    assert "Centro Escolar Alfa" in schools_page.text

    assert directors_page.status_code == 200
    assert "DOC-001" in directors_page.text
    assert "DIRECTOR" in directors_page.text

    assert students_page.status_code == 200
    assert "NIE-001" in students_page.text
    assert "NIE-002" in students_page.text


def test_student_tutor_scope_only_sees_linked_records(client, db_session):
    seed_academic_fixture(db_session)
    admin = admin_user(db_session)
    create_user(
        db_session,
        UserCreate(
            email="familia@example.org",
            full_name="Familia Uno",
            password="Tutor!234",
            role_code="student_tutor",
            student_tutor_id=300,
        ),
        admin,
    )

    tutor_user = db_session.scalar(select(User).where(User.email == "familia@example.org"))
    existing_link = db_session.scalar(
        select(UserStudentTutorLink).where(
            UserStudentTutorLink.user_id == tutor_user.id,
            UserStudentTutorLink.student_tutor_id == 300,
        )
    )
    assert existing_link is not None

    login(client, "familia@example.org", "Tutor!234")

    students_page = client.get("/students")
    tutors_page = client.get("/tutors")
    linked_student = client.get("/students/NIE-001")
    hidden_student = client.get("/students/NIE-002")

    assert students_page.status_code == 200
    assert "NIE-001" in students_page.text
    assert "NIE-002" not in students_page.text

    assert tutors_page.status_code == 200
    assert "Rosa Elena Garcia" in tutors_page.text

    assert linked_student.status_code == 200
    assert "Ana Garcia" in linked_student.text

    assert hidden_student.status_code == 404


def test_large_derived_views_and_reports_are_capped(db_session):
    seed_academic_fixture(db_session)
    admin = admin_user(db_session)

    extra_students = []
    extra_enrollments = []
    extra_assignments = []
    for idx in range(250):
        nie = f"NIE-L{idx:03d}"
        grade = f"G-{idx:03d}"
        section = f"S-{idx:03d}"
        extra_students.append(
            Student(
                id=1000 + idx,
                nie=nie,
                first_name1="Alumno",
                last_name1=f"Lote{idx:03d}",
            )
        )
        extra_enrollments.append(
            StudentEnrollment(
                id=2000 + idx,
                nie=nie,
                school_code="SCH-A",
                academic_year=2026,
                section_code=section,
                grade_label=grade,
                modality="PRESENCIAL",
                submodality="REGULAR",
            )
        )
        extra_assignments.append(
            TeacherAssignment(
                id=3000 + idx,
                id_persona="DOC-002",
                school_code="SCH-A",
                academic_year=2026,
                component_type="DOCENTE",
                grade_label=grade,
                section_id=section,
                section_name=section,
                shift="MANANA",
            )
        )

    db_session.add_all(extra_students + extra_enrollments + extra_assignments)
    db_session.commit()

    derived_grades = derive_grade_catalog_view(db_session, admin)
    derived_sections = derive_section_catalog_view(db_session, admin)
    reports = build_reports(db_session, admin)

    assert len(derived_grades) == 200
    assert len(derived_sections) == 200
    assert len(reports["teachers_by_school"]) <= 100
    assert len(reports["students_by_school"]) <= 100
    assert len(reports["enrollments_by_grade"]) == 200


def test_operational_lists_use_pagination_and_school_navigation_buttons_render(client, db_session):
    seed_academic_fixture(db_session)

    extra_schools = []
    extra_teachers = []
    extra_students = []
    extra_assignments = []
    extra_enrollments = []

    for idx in range(16):
        extra_schools.append(
            School(
                code=f"SCH-P{idx:02d}",
                name=f"Centro Escolar Serie {idx:02d}",
                sector="PUBLICO",
                zone="URBANA",
            )
        )
        extra_teachers.append(
            Teacher(
                id=500 + idx,
                id_persona=f"DOC-P{idx:02d}",
                first_names="Docente",
                last_names=f"Pagina {idx:02d}",
            )
        )
        extra_students.append(
            Student(
                id=700 + idx,
                nie=f"NIE-P{idx:02d}",
                first_name1="Alumno",
                last_name1=f"Pagina {idx:02d}",
            )
        )
        extra_assignments.append(
            TeacherAssignment(
                id=900 + idx,
                id_persona=f"DOC-P{idx:02d}",
                school_code="SCH-A",
                academic_year=2026,
                component_type="DIRECTOR",
                grade_label=f"Z-{idx:02d}",
                section_id=f"S-{idx:02d}",
                section_name=f"S-{idx:02d}",
                shift="MANANA",
            )
        )
        extra_enrollments.append(
            StudentEnrollment(
                id=1100 + idx,
                nie=f"NIE-P{idx:02d}",
                school_code="SCH-A",
                academic_year=2026,
                section_code=f"S-{idx:02d}",
                grade_label=f"Z-{idx:02d}",
                modality="PRESENCIAL",
                submodality="REGULAR",
            )
        )

    db_session.add_all(extra_schools + extra_teachers + extra_students + extra_assignments + extra_enrollments)
    db_session.commit()

    login(client, "admin@example.org", "Admin!234")

    schools_page = client.get("/schools")
    schools_page_2 = client.get("/schools?page=2")
    teachers_page = client.get("/teachers")
    teachers_page_2 = client.get("/teachers?page=2")
    students_page = client.get("/students")
    students_page_2 = client.get("/students?page=2")
    assignments_page = client.get("/assignments")
    assignments_page_2 = client.get("/assignments?page=2")
    enrollments_page = client.get("/enrollments")
    enrollments_page_2 = client.get("/enrollments?page=2")
    directors_page = client.get("/directors")
    directors_page_2 = client.get("/directors?page=2")
    school_detail = client.get("/schools/SCH-A")

    assert schools_page.status_code == 200
    assert "Página 1 de 2" in schools_page.text
    assert "Centro Escolar Serie 15" not in schools_page.text

    assert schools_page_2.status_code == 200
    assert "Página 2 de 2" in schools_page_2.text
    assert "Centro Escolar Serie 15" in schools_page_2.text

    assert teachers_page.status_code == 200
    assert teachers_page_2.status_code == 200
    assert "Página 1 de 2" in teachers_page.text
    assert "Página 2 de 2" in teachers_page_2.text
    assert teachers_page.text != teachers_page_2.text

    assert students_page.status_code == 200
    assert students_page_2.status_code == 200
    assert "Página 1 de 2" in students_page.text
    assert "Página 2 de 2" in students_page_2.text
    assert students_page.text != students_page_2.text

    assert assignments_page.status_code == 200
    assert assignments_page_2.status_code == 200
    assert "Página 1 de 2" in assignments_page.text
    assert "Página 2 de 2" in assignments_page_2.text
    assert assignments_page.text != assignments_page_2.text

    assert enrollments_page.status_code == 200
    assert enrollments_page_2.status_code == 200
    assert "Página 1 de 2" in enrollments_page.text
    assert "Página 2 de 2" in enrollments_page_2.text
    assert enrollments_page.text != enrollments_page_2.text

    assert directors_page.status_code == 200
    assert directors_page_2.status_code == 200
    assert "Página 1 de 2" in directors_page.text
    assert "Página 2 de 2" in directors_page_2.text
    assert directors_page.text != directors_page_2.text

    assert school_detail.status_code == 200
    assert 'class="button nav-action"' in school_detail.text
