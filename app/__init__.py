from __future__ import annotations

from flask import Flask

from app.config import Config
from app.extensions import db
from app.routes import routes
from app.services import ensure_ingestion_status, load_instruments


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(
        __name__,
        template_folder="templates",
    )

    app.config.from_object(Config)

    db.init_app(app)
    app.register_blueprint(routes)

    with app.app_context():
        db.create_all()

        instrument_count = load_instruments(
            app.config["INSTRUMENT_FILE"]
        )

        ensure_ingestion_status()

        app.logger.info(
            "Loaded %s instrument records",
            instrument_count,
        )

    return app