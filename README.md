# Edu Registry Monolith

Sistema de Gestión Escolar monolítico construido con FastAPI, SQLAlchemy, MySQL, Jinja2 SSR, Docker y Google Cloud. El proyecto usa un enfoque de compatibilidad primero: conserva el esquema heredado real, añade tablas nuevas solo como extensión segura y evita cambios destructivos sobre la base existente.

## 1. Descripción del proyecto

Este repositorio concentra backend, frontend SSR, autenticación, módulos académicos e importación de datos dentro de un solo despliegue monolítico.

Objetivos de infraestructura de esta base:

- desarrollo local con Docker
- desarrollo local sin Docker
- healthchecks y arranque claro
- configuración por variables de entorno
- despliegue futuro en Google Cloud App Engine Flexible
- documentación operativa y troubleshooting

## 2. Stack

- Python 3.11
- FastAPI
- Jinja2 SSR
- SQLAlchemy ORM
- MySQL 8
- PyMySQL
- Gunicorn + Uvicorn Worker
- Docker
- Docker Compose
- Google Cloud App Engine Flexible

## 3. Arquitectura monolítica

El proyecto es monolítico por diseño:

- backend y frontend viven en el mismo código
- FastAPI expone rutas SSR y endpoints auxiliares
- Jinja2 renderiza la interfaz del sistema
- la base heredada se respeta como fuente principal de escuelas, docentes, asignaciones, alumnos y matrículas
- las capacidades nuevas viven en tablas complementarias, no en reemplazos destructivos

## 4. Estructura de carpetas

```text
.
├── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── app.yaml
├── main.py
├── requirements.txt
├── .env.example
├── scripts/
├── tests/
└── app/
    ├── main.py
    ├── auth/
    ├── config/
    ├── core/
    ├── db/
    ├── models/
    ├── repositories/
    ├── routes/
    ├── schemas/
    ├── services/
    ├── static/
    ├── templates/
    └── utils/
```

## 5. Variables de entorno

Copie `.env.example` a `.env` y ajuste valores según su entorno.

Variables mínimas:

- `APP_ENV`
- `APP_HOST`
- `APP_PORT`
- `SECRET_KEY`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_DRIVER`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Variables operativas adicionales ya soportadas:

- `APP_NAME`
- `DATABASE_URL`
- `DB_INSTANCE_CONNECTION_NAME`
- `DB_SOCKET_DIR`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_FULL_NAME`
- `CREATE_SCHEMA_ON_STARTUP`
- `SQL_ECHO`
- `GUNICORN_WORKERS`
- `GUNICORN_TIMEOUT`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PORT_FORWARD`
- `GOOGLE_CLOUD_PROJECT`
- `IMPORT_SOURCE_DIR`
- `IMPORT_ZIP_FILE`

Ejemplo base:

```env
APP_NAME=Edu Registry Monolith
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
SECRET_KEY=change-this-in-production
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120

ADMIN_EMAIL=admin@example.org
ADMIN_PASSWORD=Admin!234
ADMIN_FULL_NAME=Administrador General

DB_DRIVER=mysql+pymysql
DB_HOST=edu-registry-monolith-db
DB_PORT=3306
DB_NAME=edu_reg
DB_USER=edu_user
DB_PASSWORD=CHANGE_ME
DATABASE_URL=
DB_INSTANCE_CONNECTION_NAME=
DB_SOCKET_DIR=/cloudsql

SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=

CREATE_SCHEMA_ON_STARTUP=1
SQL_ECHO=0
MYSQL_ROOT_PASSWORD=root
MYSQL_PORT_FORWARD=3307
GOOGLE_CLOUD_PROJECT=

IMPORT_SOURCE_DIR=
IMPORT_ZIP_FILE=
```

## 6. Cómo correr con Docker

Primera vez:

```bash
cp .env.example .env
docker compose up --build
```

El `docker-compose.yml` principal es el entorno base tipo producción local:

- app con Gunicorn
- MySQL 8 con volumen persistente
- red dedicada
- healthchecks para base y aplicación

Puertos por defecto:

- app: `8000`
- mysql host: `3307`

Health endpoints disponibles:

- `/healthz`
- `/readyz`

## 7. Cómo correr sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Para apuntar a una MySQL externa:

- ajuste `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- o use `DATABASE_URL` completa si necesita un DSN específico

## 8. Comandos útiles

Entorno base:

```bash
docker compose up --build
docker compose down
docker compose logs -f edu-registry-monolith-app
docker compose logs -f edu-registry-monolith-db
docker compose ps
```

Entorno de desarrollo con recarga:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Pruebas:

```bash
pytest -q
python -m py_compile $(rg --files -g '*.py')
```

Importación:

```bash
python scripts/import_all.py --dry-run
python scripts/import_schools.py --dry-run
```

## 9. Cómo conectar a MySQL

### Desarrollo local con Compose

Use los valores por defecto del `.env`:

- `DB_HOST=edu-registry-monolith-db`
- `DB_PORT=3306`

Desde su host local, el puerto expuesto por defecto es:

- `127.0.0.1:3307`

### MySQL remota

Puede apuntar el monolito a una base remota cambiando:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

### Cloud SQL en Google Cloud

Para App Engine Flexible, el proyecto ya soporta socket Unix usando:

- `DB_INSTANCE_CONNECTION_NAME`
- `DB_SOCKET_DIR=/cloudsql`

Cuando `DB_INSTANCE_CONNECTION_NAME` tiene valor, la app construye automáticamente el DSN por socket Unix.

## 10. Cómo usar importadores

Importadores disponibles:

- `scripts/import_schools.py`
- `scripts/import_teachers.py`
- `scripts/import_teacher_assignments.py`
- `scripts/import_students.py`
- `scripts/import_student_enrollments.py`
- `scripts/import_all.py`

Los CSV heredados reales usan delimitador `;`.

Flujo recomendado:

```bash
python scripts/import_all.py --zip-file ~/Downloads/data_proyecto_escuelas.zip --dry-run
python scripts/import_all.py --zip-file ~/Downloads/data_proyecto_escuelas.zip --report-dir logs/imports
```

Buenas prácticas de importación:

- correr primero en staging
- usar `--dry-run` antes de cualquier carga real
- revisar reportes `.json` y `.txt`
- validar relaciones inválidas y duplicados antes de continuar

## 11. Cómo levantar la app

Con Docker:

```bash
docker compose up --build
```

Con Docker y recarga:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Sin Docker:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

URLs típicas:

- aplicación: `http://localhost:8000`
- healthcheck básico: `http://localhost:8000/healthz`
- readiness con prueba de base: `http://localhost:8000/readyz`

## 12. Cómo desplegar en Google Cloud

El repositorio incluye [app.yaml](/Users/diegovelasquez/Documents/education_classv2/app.yaml) y [Dockerfile](/Users/diegovelasquez/Documents/education_classv2/Dockerfile) para App Engine Flexible con runtime custom.

### Recomendación de despliegue

1. Crear el proyecto y habilitar App Engine Flexible.
2. Crear o identificar la instancia Cloud SQL MySQL.
3. Crear una cuenta de servicio dedicada para el despliegue o para la versión.
4. Otorgar permisos mínimos necesarios:
   - acceso a Cloud SQL
   - Logs Writer
   - Monitoring Metric Writer
   - Storage Object Viewer
5. Ajustar `app.yaml`:
   - `beta_settings.cloud_sql_instances`
   - `DB_INSTANCE_CONNECTION_NAME`
   - `GOOGLE_CLOUD_PROJECT`
   - placeholders de secretos
6. Inyectar secretos fuera del repositorio.
7. Desplegar con:

```bash
gcloud app deploy app.yaml
```

### Imagen y runtime

- `runtime: custom`
- `env: flex`
- App Engine construye la imagen a partir del `Dockerfile`
- `entrypoint` usa Gunicorn sobre `main:app`

### Manejo de secretos

Este proyecto lee secretos desde variables de entorno. Recomendación operativa:

- no guardar secretos reales en `app.yaml`
- usar Secret Manager y su proceso de inyección desde CI/CD o pipeline de despliegue
- mantener solo placeholders en el repositorio

### Cloud SQL

`app.yaml` ya incluye la estructura necesaria para Cloud SQL por socket Unix:

- `beta_settings.cloud_sql_instances`
- `DB_SOCKET_DIR=/cloudsql`
- `DB_INSTANCE_CONNECTION_NAME`

## 13. Naming de contenedores

Nombres obligatorios ya aplicados:

- compose project: `edu-registry-monolith`
- app service: `edu-registry-monolith-app`
- db service: `edu-registry-monolith-db`
- network: `edu-registry-monolith-net`
- volume: `edu-registry-monolith-mysql-data`

## 14. Buenas prácticas

- mantener secretos fuera del control de versiones
- usar `.env` local y `.env.example` como contrato de configuración
- usar `docker-compose.yml` como entorno base y `docker-compose.dev.yml` solo para recarga y bind mounts
- no ejecutar cambios destructivos sobre el esquema heredado
- dejar `CREATE_SCHEMA_ON_STARTUP=0` en entornos productivos sensibles
- probar importadores con `--dry-run`
- monitorear `/healthz` y `/readyz`
- revisar que MySQL local use `utf8mb4` para soportar acentos y datos heredados

## 15. Troubleshooting

### La app no arranca en Docker

- revise `docker compose logs -f edu-registry-monolith-app`
- confirme que `.env` exista
- confirme que `SECRET_KEY` y credenciales DB estén definidas

### `/readyz` devuelve 503

- la app levantó, pero no puede abrir conexión a la base
- revise `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- si usa Cloud SQL, valide `DB_INSTANCE_CONNECTION_NAME`

### MySQL local no acepta conexiones

- revise `docker compose logs -f edu-registry-monolith-db`
- confirme `MYSQL_ROOT_PASSWORD`
- confirme que el puerto host `3307` no esté ocupado

### App Engine despliega pero no conecta a Cloud SQL

- revise `beta_settings.cloud_sql_instances`
- revise `DB_INSTANCE_CONNECTION_NAME`
- confirme permisos de la cuenta de servicio desplegada
- confirme que la instancia Cloud SQL permita el método de conexión elegido

### Cambios de código no se reflejan en desarrollo

- use `docker-compose.dev.yml`
- confirme que el bind mount `.:/app` esté activo
- reinicie el contenedor si cambió dependencias

## Compatibilidad del esquema

### Tablas heredadas reales

- `schools`
- `teachers`
- `teacher_assignments`
- `students`
- `student_enrollments`

### Tablas nuevas del monolito

- `roles`
- `users`
- `password_reset_tokens`
- `academic_year_catalogs`
- `grade_catalogs`
- `section_catalogs`
- `modality_catalogs`
- `subject_catalogs`
- `student_tutors`
- `student_tutor_student_links`
- `user_student_tutor_links`
- `grade_records`
- `report_cards`
- `report_card_items`
- `announcements`
- `access_recovery_tokens`

El enfoque es compatible y no destructivo:

- no se reemplazan tablas heredadas
- no se cambia la identidad real de escuela, docente o alumno
- las funcionalidades nuevas se acoplan por claves seguras como `school_code`, `id_persona` y `nie`

## Verificación local reciente

- `py_compile`: OK
- `pytest -q`: OK
- `docker compose config`: validar después de cualquier cambio de infraestructura
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml config`: validar override de desarrollo

## Fuentes oficiales consultadas

- [App Engine flexible `app.yaml` reference](https://docs.cloud.google.com/appengine/docs/flexible/reference/app-yaml)
- [Configuring custom runtimes with `app.yaml`](https://docs.cloud.google.com/appengine/docs/flexible/custom-runtimes/configuring-your-app-with-app-yaml)
- [Build custom runtimes in App Engine Flexible](https://cloud.google.com/appengine/docs/flexible/custom-runtimes/build)
- [Use Cloud SQL from App Engine Flexible](https://cloud.google.com/appengine/docs/flexible/use-cloud-sql)
- [App Engine Flexible access control and service accounts](https://cloud.google.com/appengine/docs/flexible/access-control)
