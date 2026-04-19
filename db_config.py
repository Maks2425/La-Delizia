"""Build the SQLAlchemy DB URL from environment (see .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine.url import URL

_root = Path(__file__).resolve().parent
load_dotenv(_root / ".env")


def get_database_url() -> URL:
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD")
    if password is not None and password == "":
        password = None
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    database = os.environ.get("MYSQL_DATABASE", "online_restaurant")
    return URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
    )


if __name__ == "__main__":
    from sqlalchemy import create_engine, text

    engine = create_engine(get_database_url())
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("MySQL connection OK.")
    except Exception as exc:
        print("Connection failed:", exc)
        raise
