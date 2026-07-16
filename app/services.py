from __future__ import annotations

import csv
from pathlib import Path

from app.extensions import db
from app.models import IngestionStatus, Instrument


def load_instruments(csv_path: Path) -> int:
    """Load or update synthetic instrument reference data."""

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Instrument file does not exist: {csv_path}"
        )

    loaded_count = 0

    with csv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        required_columns = {
            "instrument_id",
            "long_name",
            "short_name",
            "country",
            "sector",
            "industry",
            "exchange",
            "type",
            "currency",
        }

        actual_columns = set(reader.fieldnames or [])

        missing_columns = required_columns - actual_columns

        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))

            raise ValueError(
                "Instrument CSV is missing required columns: "
                f"{missing_text}"
            )

        for row in reader:
            instrument = db.session.get(
                Instrument,
                row["instrument_id"],
            )

            if instrument is None:
                instrument = Instrument(
                    instrument_id=row["instrument_id"],
                )

                db.session.add(instrument)

            instrument.long_name = row["long_name"]
            instrument.short_name = row["short_name"]
            instrument.country = row["country"]
            instrument.sector = row["sector"]
            instrument.industry = row["industry"]
            instrument.exchange = row["exchange"]
            instrument.instrument_type = row["type"]
            instrument.currency = row["currency"]

            loaded_count += 1

    db.session.commit()

    return loaded_count


def ensure_ingestion_status() -> IngestionStatus:
    """Create the singleton ingestion-status row when needed."""

    status = db.session.get(IngestionStatus, 1)

    if status is None:
        status = IngestionStatus(id=1)
        db.session.add(status)
        db.session.commit()

    return status