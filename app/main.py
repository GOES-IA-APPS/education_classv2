from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.core.bootstrap import initialize_phase1
from app.db import Base, SessionLocal, engine
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.create_schema_on_startup:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            initialize_phase1(db)
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Sistema de Gestion Escolar monolitico compatible con el esquema heredado.",
        lifespan=lifespan,
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.exception_handler(OperationalError)
    async def database_unavailable_handler(_, __):
        return HTMLResponse(
            content="Base de datos espejo no disponible temporalmente. Intenta de nuevo en unos segundos.",
            status_code=503,
        )

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.app_env,
        }

    @app.get("/readyz", include_in_schema=False)
    def readyz():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {
                "status": "ready",
                "database": "ok",
            }
        except Exception as exc:  # pragma: no cover - defensive infrastructure guard
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "database": "error",
                    "error_type": exc.__class__.__name__,
                },
            )

    app.include_router(router)
    return app


app = create_app()
