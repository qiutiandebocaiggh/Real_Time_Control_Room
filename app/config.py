from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env")


def resolve_project_path(value: str) -> Path:
    """Resolve a path relative to the project root."""
    path = Path(value)

    if path.is_absolute():
        return path

    return BASE_DIR / path


class Config:
    """Application configuration loaded from environment variables."""

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        (
            "postgresql+psycopg2://"
            "control_room:control_room@localhost:5433/control_room"
        ),
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STREAM_HOST = os.getenv("STREAM_HOST", "127.0.0.1")
    STREAM_PORT = int(os.getenv("STREAM_PORT", "1337"))
    STREAM_RECONNECT_SECONDS = float(
        os.getenv("STREAM_RECONNECT_SECONDS", "3")
)

    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))

    INSTRUMENT_FILE = resolve_project_path(
        os.getenv(
            "INSTRUMENT_FILE",
            "simulator/instruments.csv",
        )
    )

    DASHBOARD_REFRESH_MS = int(
        os.getenv("DASHBOARD_REFRESH_MS", "2000")
    )

    DATA_FRESHNESS_THRESHOLD_SECONDS = int(
        os.getenv(
            "DATA_FRESHNESS_THRESHOLD_SECONDS",
            "10",
        )
    )