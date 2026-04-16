from __future__ import annotations

import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def build_connection_string(database: str | None = None) -> str:
    driver = os.getenv("WWI_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("WWI_SQL_SERVER", "localhost")
    default_database = os.getenv("WWI_SQL_DATABASE", "WideWorldImportersDW")
    database_name = database or default_database

    username = os.getenv("WWI_SQL_USERNAME")
    password = os.getenv("WWI_SQL_PASSWORD")
    trusted = os.getenv("WWI_SQL_TRUSTED_CONNECTION", "yes")
    trust_cert = os.getenv("WWI_SQL_TRUST_SERVER_CERTIFICATE", "yes")

    if username and password:
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database_name};"
            f"UID={username};"
            f"PWD={password};"
            f"TrustServerCertificate={trust_cert};"
        )

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database_name};"
        f"Trusted_Connection={trusted};"
        f"TrustServerCertificate={trust_cert};"
    )


def get_connection(database: str | None = None) -> pyodbc.Connection:
    conn_str = build_connection_string(database)
    return pyodbc.connect(conn_str)