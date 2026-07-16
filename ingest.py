import logging

from app import create_app
from app.ingestion import run_ingestion

app = create_app()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    with app.app_context():
        run_ingestion(
            host=app.config["STREAM_HOST"],
            port=app.config["STREAM_PORT"],
            reconnect_seconds=app.config[
                "STREAM_RECONNECT_SECONDS"
            ],
        )