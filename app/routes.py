from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import select

from app.extensions import db
from app.models import IngestionStatus, Instrument, Price, Trade

routes = Blueprint(
    "routes",
    __name__,
)


@routes.get("/")
def dashboard():
    return render_template(
        "dashboard.html",
        refresh_ms=current_app.config["DASHBOARD_REFRESH_MS"],
        freshness_threshold_seconds=current_app.config[
            "DATA_FRESHNESS_THRESHOLD_SECONDS"
        ],
    )


@routes.get("/api/health")
def health():
    status = db.session.get(IngestionStatus, 1)

    return jsonify(
        {
            "status": "ok",
            "instrument_count": db.session.scalar(
                select(db.func.count(Instrument.instrument_id))
            ),
            "trade_count": db.session.scalar(
                select(db.func.count(Trade.trade_id))
            ),
            "price_count": db.session.scalar(
                select(db.func.count(Price.id))
            ),
            "ingestion": (
                status.as_dict()
                if status
                else None
            ),
        }
    )


@routes.get("/api/instruments")
def instruments():
    rows = db.session.scalars(
        select(Instrument).order_by(Instrument.short_name)
    ).all()

    return jsonify(
        [row.as_dict() for row in rows]
    )


@routes.get("/api/trades/latest")
def latest_trades():
    limit = min(
        request.args.get(
            "limit",
            default=50,
            type=int,
        ),
        200,
    )

    rows = db.session.scalars(
        select(Trade)
        .order_by(Trade.event_time.desc())
        .limit(limit)
    ).all()

    return jsonify(
        [row.as_dict() for row in rows]
    )


@routes.get("/api/prices/latest")
def latest_prices():
    limit = min(
        request.args.get(
            "limit",
            default=50,
            type=int,
        ),
        200,
    )

    rows = db.session.scalars(
        select(Price)
        .order_by(Price.event_time.desc())
        .limit(limit)
    ).all()

    return jsonify(
        [row.as_dict() for row in rows]
    )


@routes.get("/api/cash-flow")
def cash_flow():
    currency = request.args.get(
        "currency",
        default="EUR",
        type=str,
    ).upper()

    rows = db.session.scalars(
        select(Trade)
        .where(Trade.currency == currency)
        .order_by(Trade.event_time.asc())
    ).all()

    running_cash_flow = 0.0
    output = []

    for row in rows:
        running_cash_flow += row.signed_notional

        output.append(
            {
                "time": row.event_time.isoformat(),
                "net_cash_flow": round(
                    running_cash_flow,
                    2,
                ),
                "trade_id": row.trade_id,
                "instrument_id": row.instrument_id,
                "short_name": (
                    row.instrument.short_name
                    if row.instrument
                    else None
                ),
                "side": row.side,
                "notional": round(row.notional, 2),
                "currency": row.currency,
            }
        )

    return jsonify(output[-300:])