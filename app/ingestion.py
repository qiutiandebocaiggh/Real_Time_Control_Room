from __future__ import annotations

import json
import logging
import socket
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Instrument, Price, Trade
from app.services import ensure_ingestion_status

logger = logging.getLogger(__name__)


class EventValidationError(ValueError):
    """Raised when an incoming stream event is structurally invalid."""


def parse_event_time(value: Any) -> datetime:
    """Parse a timezone-aware ISO-8601 event timestamp."""

    if not isinstance(value, str) or not value.strip():
        raise EventValidationError(
            "Event timestamp must be a non-empty string"
        )

    normalized = value.replace("Z", "+00:00")

    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise EventValidationError(
            f"Invalid event timestamp: {value}"
        ) from exc

    if timestamp.tzinfo is None:
        raise EventValidationError(
            "Event timestamp must include a timezone"
        )

    return timestamp


def require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    """Validate that a value is a JSON object."""

    if not isinstance(value, dict):
        raise EventValidationError(
            f"{field_name} must be a JSON object"
        )

    return value


def require_string(value: Any, field_name: str) -> str:
    """Validate and normalize a required string field."""

    if not isinstance(value, str) or not value.strip():
        raise EventValidationError(
            f"{field_name} must be a non-empty string"
        )

    return value.strip()


def require_positive_number(value: Any, field_name: str) -> float:
    """Validate a positive numeric field."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EventValidationError(
            f"{field_name} must be numeric"
        )

    numeric_value = float(value)

    if numeric_value <= 0:
        raise EventValidationError(
            f"{field_name} must be greater than zero"
        )

    return numeric_value


def require_positive_integer(value: Any, field_name: str) -> int:
    """Validate a positive integer field."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise EventValidationError(
            f"{field_name} must be an integer"
        )

    if value <= 0:
        raise EventValidationError(
            f"{field_name} must be greater than zero"
        )

    return value


def get_instrument(instrument_id: str) -> Instrument:
    """Return a known instrument or reject the incoming event."""

    instrument = db.session.get(
        Instrument,
        instrument_id,
    )

    if instrument is None:
        raise EventValidationError(
            f"Unknown instrument_id: {instrument_id}"
        )

    return instrument


def update_connection_status(
    connection_status: str,
    last_error: str | None = None,
) -> None:
    """Persist the current stream connection state."""

    status = ensure_ingestion_status()
    status.connection_status = connection_status
    status.last_error = last_error

    db.session.commit()


def record_invalid_message(error_message: str) -> None:
    """Increment the invalid-message counter."""

    status = ensure_ingestion_status()
    status.invalid_message_count += 1
    status.last_error = error_message

    db.session.commit()


def record_duplicate_trade(event_time: datetime) -> None:
    """Increment the duplicate-trade counter."""

    status = ensure_ingestion_status()
    status.duplicate_trade_count += 1
    status.last_event_at = event_time
    status.last_error = None

    db.session.commit()


def process_trade(
    data: dict[str, Any],
    raw_json: str,
) -> str:
    """Validate and persist a trade event."""

    trade_id = require_string(
        data.get("trade_id"),
        "trade_id",
    )

    instrument_id = require_string(
        data.get("instrument_id"),
        "instrument_id",
    )

    instrument = get_instrument(instrument_id)

    price = require_positive_number(
        data.get("price"),
        "price",
    )

    volume = require_positive_integer(
        data.get("volume"),
        "volume",
    )

    side = require_string(
        data.get("side"),
        "side",
    ).upper()

    if side not in {"BUY", "SELL"}:
        raise EventValidationError(
            "side must be BUY or SELL"
        )

    currency = require_string(
        data.get("currency"),
        "currency",
    ).upper()

    if currency != instrument.currency:
        raise EventValidationError(
            "Trade currency does not match instrument currency: "
            f"{currency} != {instrument.currency}"
        )

    event_time = parse_event_time(
        data.get("date")
    )

    existing_trade = db.session.get(
        Trade,
        trade_id,
    )

    if existing_trade is not None:
        record_duplicate_trade(event_time)
        return "duplicate"

    notional = price * volume

    signed_notional = (
        -notional
        if side == "BUY"
        else notional
    )

    trade = Trade(
        trade_id=trade_id,
        instrument_id=instrument_id,
        price=price,
        volume=volume,
        side=side,
        currency=currency,
        event_time=event_time,
        notional=notional,
        signed_notional=signed_notional,
        raw_json=raw_json,
    )

    status = ensure_ingestion_status()
    status.processed_trade_count += 1
    status.last_event_at = event_time
    status.last_error = None

    db.session.add(trade)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        record_duplicate_trade(event_time)
        return "duplicate"

    return "stored_trade"


def process_price(
    data: dict[str, Any],
    raw_json: str,
) -> str:
    """Validate and persist a market-price event."""

    instrument_id = require_string(
        data.get("instrument_id"),
        "instrument_id",
    )

    get_instrument(instrument_id)

    price_value = require_positive_number(
        data.get("price"),
        "price",
    )

    event_time = parse_event_time(
        data.get("date")
    )

    price = Price(
        instrument_id=instrument_id,
        price=price_value,
        event_time=event_time,
        raw_json=raw_json,
    )

    status = ensure_ingestion_status()
    status.processed_price_count += 1
    status.last_event_at = event_time
    status.last_error = None

    db.session.add(price)
    db.session.commit()

    return "stored_price"


def process_event(
    event: dict[str, Any],
    raw_json: str,
) -> str:
    """Route an incoming event to the correct processor."""

    event_type = require_string(
        event.get("type"),
        "type",
    ).lower()

    data = require_mapping(
        event.get("data"),
        "data",
    )

    if event_type == "trade":
        return process_trade(
            data=data,
            raw_json=raw_json,
        )

    if event_type == "price":
        return process_price(
            data=data,
            raw_json=raw_json,
        )

    raise EventValidationError(
        f"Unsupported event type: {event_type}"
    )


def process_line(line: str) -> str:
    """Parse, validate and persist one NDJSON line."""

    raw_json = line.strip()

    if not raw_json:
        error_message = "Received an empty stream message"

        record_invalid_message(error_message)
        logger.warning(error_message)

        return "invalid"

    try:
        decoded = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        error_message = (
            "Invalid JSON received at "
            f"character {exc.pos}: {exc.msg}"
        )

        record_invalid_message(error_message)
        logger.warning(error_message)

        return "invalid"

    try:
        event = require_mapping(
            decoded,
            "event",
        )

        result = process_event(
            event=event,
            raw_json=raw_json,
        )

    except EventValidationError as exc:
        error_message = str(exc)

        record_invalid_message(error_message)
        logger.warning(
            "Rejected stream event: %s",
            error_message,
        )

        return "invalid"

    if result == "duplicate":
        logger.info(
            "Rejected duplicate trade event"
        )

    return result


def run_ingestion(
    host: str,
    port: int,
    reconnect_seconds: float,
) -> None:
    """Continuously connect to the TCP stream and ingest events."""

    logger.info(
        "Starting ingestion worker for %s:%s",
        host,
        port,
    )

    while True:
        try:
            update_connection_status(
                connection_status="connecting",
                last_error=None,
            )

            with socket.create_connection(
                (host, port),
                timeout=10,
            ) as connection:
                connection.settimeout(None)

                update_connection_status(
                    connection_status="connected",
                    last_error=None,
                )

                logger.info(
                    "Connected to stream at %s:%s",
                    host,
                    port,
                )

                with connection.makefile(
                    "r",
                    encoding="utf-8",
                ) as stream:
                    for line in stream:
                        process_line(line)

                raise ConnectionError(
                    "The source stream closed the connection"
                )

        except KeyboardInterrupt:
            update_connection_status(
                connection_status="stopped",
                last_error=None,
            )

            logger.info(
                "Ingestion worker stopped"
            )

            return

        except (ConnectionError, OSError) as exc:
            error_message = str(exc)

            update_connection_status(
                connection_status="disconnected",
                last_error=error_message,
            )

            logger.warning(
                "Stream unavailable: %s. "
                "Retrying in %.1f seconds.",
                error_message,
                reconnect_seconds,
            )

            time.sleep(reconnect_seconds)