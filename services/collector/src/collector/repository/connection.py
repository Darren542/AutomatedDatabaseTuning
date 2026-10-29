"""Connection management for the separate AutoTunerRepository database."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pyodbc
from dotenv import dotenv_values


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


@dataclass(frozen=True)
class RepositorySettings:
    driver: str
    server: str
    database: str
    trusted_connection: bool
    trust_server_certificate: bool
    username: str | None = None
    password: str | None = field(default=None, repr=False)

    @classmethod
    def load(cls, env_file: Path | None = None) -> "RepositorySettings":
        values = {
            **dotenv_values(env_file or Path.cwd() / ".env"),
            **os.environ,
        }

        def required(name: str, default: str | None = None) -> str:
            value = values.get(name, default)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required.")
            return value.strip()

        def boolean(name: str, default: str) -> bool:
            raw = required(name, default).lower()
            if raw in {"1", "true", "yes", "y"}:
                return True
            if raw in {"0", "false", "no", "n"}:
                return False
            raise ValueError(f"{name} must be true/false or yes/no.")

        return cls(
            driver=required(
                "AUTOTUNER_REPO_SQL_DRIVER",
                "ODBC Driver 18 for SQL Server",
            ),
            server=required(
                "AUTOTUNER_REPO_SQL_SERVER",
                r"localhost\SQLEXPRESS",
            ),
            database=required(
                "AUTOTUNER_REPO_SQL_DATABASE",
                "AutoTunerRepository",
            ),
            trusted_connection=boolean(
                "AUTOTUNER_REPO_SQL_TRUSTED_CONNECTION",
                "yes",
            ),
            trust_server_certificate=boolean(
                "AUTOTUNER_REPO_SQL_TRUST_SERVER_CERTIFICATE",
                "yes",
            ),
            username=values.get("AUTOTUNER_REPO_SQL_USERNAME") or None,
            password=values.get("AUTOTUNER_REPO_SQL_PASSWORD") or None,
        )

    def to_connection_string(self) -> str:
        parts = [
            f"DRIVER={{{self.driver}}}",
            "SERVER=" + _odbc_value(self.server),
            "DATABASE=" + _odbc_value(self.database),
            "Encrypt=yes",
            (
                "TrustServerCertificate=yes"
                if self.trust_server_certificate
                else "TrustServerCertificate=no"
            ),
            "APP=AutomatedDatabaseTuner.Repository",
        ]

        if self.username is not None and self.password is not None:
            parts.extend(
                [
                    "UID=" + _odbc_value(self.username),
                    "PWD=" + _odbc_value(self.password),
                ]
            )
        elif self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            raise ValueError(
                "Repository SQL authentication requires "
                "AUTOTUNER_REPO_SQL_USERNAME and AUTOTUNER_REPO_SQL_PASSWORD."
            )

        return ";".join(parts) + ";"


@contextmanager
def repository_connection(
    settings: RepositorySettings | None = None,
) -> Iterator[pyodbc.Connection]:
    effective = settings or RepositorySettings.load()
    connection = pyodbc.connect(
        effective.to_connection_string(),
        autocommit=False,
        timeout=10,
    )
    try:
        connection.timeout = 60
        yield connection
    finally:
        connection.close()
