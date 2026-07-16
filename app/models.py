from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)

class Instrument(db.Model):
    __tablename__ = "instruments"

    instrument_id = db.Column(
        db.String(64),
        primary_key=True,
    )

    long_name = db.Column(
        db.String(255),
        nullable=False,
    )

    short_name = db.Column(
        db.String(64),
        nullable=False,
    )

    country = db.Column(db.String(100))
    sector = db.Column(db.String(100))
    industry = db.Column(db.String(150))
    exchange = db.Column(db.String(50))

    instrument_type = db.Column(
        "type",
        db.String(50),
    )

    currency = db.Column(
        db.String(10),
        nullable=False,
    )

    def as_dict(self) -> dict:
        return {
            "instrument_id": self.instrument_id,
            "long_name": self.long_name,
            "short_name": self.short_name,
            "country": self.country,
            "sector": self.sector,
            "industry": self.industry,
            "exchange": self.exchange,
            "type": self.instrument_type,
            "currency": self.currency,
        }


class Trade(db.Model):
    __tablename__ = "trades"

    trade_id = db.Column(
        db.String(64),
        primary_key=True,
    )

    instrument_id = db.Column(
        db.String(64),
        db.ForeignKey("instruments.instrument_id"),
        nullable=False,
        index=True,
    )

    price = db.Column(
        db.Float,
        nullable=False,
    )

    volume = db.Column(
        db.Integer,
        nullable=False,
    )

    side = db.Column(
        db.String(10),
        nullable=False,
    )

    currency = db.Column(
        db.String(10),
        nullable=False,
        index=True,
    )

    event_time = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    notional = db.Column(
        db.Float,
        nullable=False,
    )

    signed_notional = db.Column(
        db.Float,
        nullable=False,
    )

    raw_json = db.Column(
        db.Text,
        nullable=False,
    )

    instrument = db.relationship(
        "Instrument",
        lazy="joined",
    )

    def as_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "instrument_id": self.instrument_id,
            "short_name": (
                self.instrument.short_name
                if self.instrument
                else None
            ),
            "long_name": (
                self.instrument.long_name
                if self.instrument
                else None
            ),
            "country": (
                self.instrument.country
                if self.instrument
                else None
            ),
            "sector": (
                self.instrument.sector
                if self.instrument
                else None
            ),
            "price": self.price,
            "volume": self.volume,
            "side": self.side,
            "currency": self.currency,
            "event_time": self.event_time.isoformat(),
            "notional": self.notional,
            "signed_notional": self.signed_notional,
        }


class Price(db.Model):
    __tablename__ = "prices"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    instrument_id = db.Column(
        db.String(64),
        db.ForeignKey("instruments.instrument_id"),
        nullable=False,
        index=True,
    )

    price = db.Column(
        db.Float,
        nullable=False,
    )

    event_time = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    raw_json = db.Column(
        db.Text,
        nullable=False,
    )

    instrument = db.relationship(
        "Instrument",
        lazy="joined",
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "instrument_id": self.instrument_id,
            "short_name": (
                self.instrument.short_name
                if self.instrument
                else None
            ),
            "currency": (
                self.instrument.currency
                if self.instrument
                else None
            ),
            "price": self.price,
            "event_time": self.event_time.isoformat(),
        }


class IngestionStatus(db.Model):
    __tablename__ = "ingestion_status"

    id = db.Column(
        db.Integer,
        primary_key=True,
        default=1,
    )

    connection_status = db.Column(
        db.String(30),
        nullable=False,
        default="not_started",
    )

    processed_trade_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    processed_price_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    duplicate_trade_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    invalid_message_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    last_event_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    last_error = db.Column(
        db.Text,
        nullable=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def as_dict(self) -> dict:
        return {
            "connection_status": self.connection_status,
            "processed_trade_count": self.processed_trade_count,
            "processed_price_count": self.processed_price_count,
            "duplicate_trade_count": self.duplicate_trade_count,
            "invalid_message_count": self.invalid_message_count,
            "last_event_at": (
                self.last_event_at.isoformat()
                if self.last_event_at
                else None
            ),
            "last_error": self.last_error,
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }