from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    app_name: str
    app_env: str
    app_host: str
    app_port: int
    secret_key: str
    admin_email: str
    admin_password: str
    admin_full_name: str
    db_driver: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    database_url_override: str | None
    db_socket_dir: str
    db_instance_connection_name: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    google_cloud_project: str
    create_schema_on_startup: bool
    sql_echo: bool

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override

        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)

        if self.db_instance_connection_name:
            socket_path = quote_plus(
                f"{self.db_socket_dir}/{self.db_instance_connection_name}"
            )
            return (
                f"{self.db_driver}://{user}:{password}@/{self.db_name}"
                f"?unix_socket={socket_path}"
            )

        return (
            f"{self.db_driver}://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Edu Registry Monolith"),
        app_env=os.getenv("APP_ENV", "development"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        secret_key=os.getenv("SECRET_KEY", "change-this-in-production"),
        admin_email=os.getenv("ADMIN_EMAIL", "admin@example.org"),
        admin_password=os.getenv("ADMIN_PASSWORD", "Admin!234"),
        admin_full_name=os.getenv("ADMIN_FULL_NAME", "Administrador General"),
        db_driver=os.getenv("DB_DRIVER", "mysql+pymysql"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_name=os.getenv("DB_NAME", "edu_reg"),
        db_user=os.getenv("DB_USER", "edu_user"),
        db_password=os.getenv("DB_PASSWORD", "change-me"),
        database_url_override=os.getenv("DATABASE_URL"),
        db_socket_dir=os.getenv("DB_SOCKET_DIR", "/cloudsql"),
        db_instance_connection_name=os.getenv("DB_INSTANCE_CONNECTION_NAME", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""),
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        create_schema_on_startup=as_bool(
            os.getenv("CREATE_SCHEMA_ON_STARTUP"), True
        ),
        sql_echo=as_bool(os.getenv("SQL_ECHO"), False),
    )


settings = get_settings()
