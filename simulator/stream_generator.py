from __future__ import annotations

import argparse
import csv
import json
import random
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    short_name: str
    currency: str
    base_price: float


def load_instruments(path: Path) -> list[Instrument]:
    """Load synthetic instrument reference data from CSV."""
    instruments: list[Instrument] = []

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for index, row in enumerate(reader):
            instruments.append(
                Instrument(
                    instrument_id=row["instrument_id"],
                    short_name=row["short_name"],
                    currency=row["currency"],
                    base_price=50.0 + index * 35.0,
                )
            )

    if not instruments:
        raise ValueError(f"No instruments found in {path}")

    return instruments


def iso_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def generate_price(
    instrument: Instrument,
    current_prices: dict[str, float],
    rng: random.Random,
) -> dict:
    """Generate a price event using a small random price movement."""
    previous_price = current_prices[instrument.instrument_id]
    movement = rng.uniform(-0.008, 0.008)

    new_price = max(0.01, previous_price * (1 + movement))
    current_prices[instrument.instrument_id] = new_price

    return {
        "type": "price",
        "data": {
            "instrument_id": instrument.instrument_id,
            "price": round(new_price, 4),
            "date": iso_timestamp(),
        },
    }


def generate_trade(
    instrument: Instrument,
    current_prices: dict[str, float],
    rng: random.Random,
) -> dict:
    """Generate a trade around the latest available market price."""
    market_price = current_prices[instrument.instrument_id]
    execution_noise = rng.uniform(-0.002, 0.002)

    return {
        "type": "trade",
        "data": {
            "trade_id": str(uuid.uuid4()),
            "instrument_id": instrument.instrument_id,
            "price": round(market_price * (1 + execution_noise), 4),
            "volume": rng.randint(100, 10_000),
            "side": rng.choice(["BUY", "SELL"]),
            "currency": instrument.currency,
            "date": iso_timestamp(),
        },
    }


def send_event(client: TextIO, event: dict) -> None:
    """Write one newline-delimited JSON event to the connected client."""
    client.write(json.dumps(event) + "\n")
    client.flush()


def serve(
    host: str,
    port: int,
    instruments: list[Instrument],
    interval_min: float,
    interval_max: float,
    duplicate_rate: float,
    seed: int,
) -> None:
    """Start a TCP server and continuously send synthetic events."""
    rng = random.Random(seed)

    current_prices = {
        instrument.instrument_id: instrument.base_price
        for instrument in instruments
    }

    previous_trade: dict | None = None

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)

        print(f"Simulator listening on {host}:{port}")
        print("Waiting for application connection...")

        while True:
            connection, address = server.accept()
            print(f"Client connected from {address[0]}:{address[1]}")

            try:
                with connection:
                    client = connection.makefile("w", encoding="utf-8")

                    while True:
                        instrument = rng.choice(instruments)

                        if previous_trade and rng.random() < duplicate_rate:
                            event = previous_trade
                            print(
                                "Sending duplicate trade:",
                                event["data"]["trade_id"],
                            )
                        elif rng.random() < 0.6:
                            event = generate_trade(
                                instrument,
                                current_prices,
                                rng,
                            )
                            previous_trade = event
                        else:
                            event = generate_price(
                                instrument,
                                current_prices,
                                rng,
                            )

                        send_event(client, event)
                        print(json.dumps(event))

                        time.sleep(
                            rng.uniform(interval_min, interval_max)
                        )

            except (
                BrokenPipeError,
                ConnectionResetError,
                ConnectionAbortedError,
            ):
                print("Client disconnected. Waiting for reconnection...")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthetic real-time operations event simulator"
    )

    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1337)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--interval-min", type=float, default=0.5)
    parser.add_argument("--interval-max", type=float, default=1.5)
    parser.add_argument("--duplicate-rate", type=float, default=0.03)

    parser.add_argument(
        "--instruments",
        type=Path,
        default=Path(__file__).with_name("instruments.csv"),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.interval_min < 0:
        raise ValueError("interval-min must be zero or greater")

    if args.interval_max < args.interval_min:
        raise ValueError(
            "interval-max must be greater than or equal to interval-min"
        )

    if not 0 <= args.duplicate_rate <= 1:
        raise ValueError("duplicate-rate must be between 0 and 1")

    instruments = load_instruments(args.instruments)

    serve(
        host=args.host,
        port=args.port,
        instruments=instruments,
        interval_min=args.interval_min,
        interval_max=args.interval_max,
        duplicate_rate=args.duplicate_rate,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()