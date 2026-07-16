import csv
import json
import socket
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

# I run this file from the project root: ~/Desktop/Ray_Sun_WEBB_Traders_Technical_Test
instrument_file = "generator/instruments.csv"

# Postgres is running in Dockerm, mapped local port 5433 to container port 5432
db_url = "postgresql+psycopg2://webb:webb@localhost:5433/webb"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the database models for instruments, trades and prices
class Instrument(db.Model):
    __tablename__ = 'instruments'
    instrument_id = db.Column(db.String, primary_key=True)
    long_name = db.Column(db.String)
    short_name = db.Column(db.String)
    country = db.Column(db.String)
    sector = db.Column(db.String)
    industry = db.Column(db.String)
    exchange = db.Column(db.String)
    type = db.Column(db.String)

    def as_dict(self):
        return {
            "instrument_id": self.instrument_id,
            "long_name": self.long_name,
            "short_name": self.short_name,
            "country": self.country,
            "sector": self.sector,
            "industry": self.industry,
            "exchange": self.exchange,
            "type": self.type

        }
    
# The Trade model includes notional and signed_notional fields to simplify PnL calculations later on
class Trade(db.Model):
    __tablename__ = 'trades'
    trade_id = db.Column(db.String, primary_key=True)
    instrument_id = db.Column(db.String)
    price = db.Column(db.Float)
    volume = db.Column(db.Integer)
    side = db.Column(db.String)
    currency = db.Column(db.String)
    event_time = db.Column(db.DateTime)
    notional = db.Column(db.Float)
    signed_notional = db.Column(db.Float)
    raw_json = db.Column(db.Text)
    def as_dict(self):
        return {
            "trade_id": self.trade_id,
            "instrument_id": self.instrument_id,
            "price": self.price,
            "volume": self.volume,
            "side": self.side,
            "currency": self.currency,
            "event_time": self.event_time.isoformat() if self.event_time else None,
            "notional": self.notional,
            "signed_notional": self.signed_notional
        }

# The Price model is simpler, just storing the latest price ticks for each instrument
class Price(db.Model):
    __tablename__ = 'prices'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    instrument_id = db.Column(db.String)
    price = db.Column(db.Float)
    event_time = db.Column(db.DateTime)
    raw_json = db.Column(db.Text)
    def as_dict(self):
        return {
            "id": self.id,
            "instrument_id": self.instrument_id,
            "price": self.price,
            "event_time": self.event_time.isoformat() if self.event_time else None
        }
# This function loads the instruments from the CSV file into the database, but only if they are not already loaded
def load_instruments():
    count = Instrument.query.count()
    if count > 0:
        print("instruments already loaded:", count)
        return
    print("loading instruments from csv:", instrument_file)

    with open(instrument_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = Instrument(
                instrument_id=row["instrument_id"],
                long_name=row["long_name"],
                short_name=row["short_name"],
                country=row["country"],
                sector=row["sector"],
                industry=row["industry"],
                exchange=row["exchange"],
                type=row["type"]
            )
            db.session.add(item)
        db.session.commit()
        print("finished loading instruments")

# This function creates the database tables and loads the instruments. It is called once at startup.
def setup_database():
    db.create_all()
    load_instruments()

# This function parses the date string from the AMD stream into a Python datetime object. The AMD stream uses ISO format, so we can use fromisoformat directly.
def parse_time(date_text):
    return datetime.fromisoformat(date_text)

#  This function saves a trade message from the AMD stream into the database. It calculates the notional and signed notional values to simplify PnL calculations later on.
def save_trade(data, raw_line):
    price = float(data["price"])
    volume = int(data["volume"])
    notional = price * volume
    if data["side"] == "BUY":
        signed_notional = -notional
    else:
        signed_notional = notional

    trade = Trade(
        trade_id=data["trade_id"],
        instrument_id=data["instrument_id"],
        price=price,
        volume=volume,
        side=data["side"],
        currency=data.get("currency"),
        event_time=parse_time(data["date"]),
        notional=notional,
        signed_notional=signed_notional,
        raw_json=raw_line,
    )
    db.session.merge(trade)
    db.session.commit()

# This function saves a price tick message from the AMD stream into the database. It does not attempt to keep only the latest price for each instrument, but simply stores all price ticks with their timestamps.
def save_price(data, raw_line):
    price_tick = Price(
        instrument_id=data["instrument_id"],
        price=float(data["price"]),
        event_time=parse_time(data["date"]),
        raw_json=raw_line,
    )
    db.session.add(price_tick)
    db.session.commit()

# This function connects to the AMD stream via a TCP socket, reads the incoming messages line by line, and dispatches them to the appropriate save functions based on their type (trade or price). It runs in a separate thread to avoid blocking the main Flask application.
def read_stream():
    print("connecting to AMD stream...")

    with app.app_context():
        with socket.create_connection(("127.0.0.1", 1337)) as s:
            file = s.makefile("r")

            for line in file:
                line = line.strip()
                if line == "":
                    continue
                try:
                    message = json.loads(line)
                    message_type = message.get("type")
                    data = message.get("data", {})
                                       
                    if message_type == "trade":
                        save_trade(data, line)
                    elif message_type == "price":
                        save_price(data, line)
                except Exception as e:
                    db.session.rollback()
                    print("error while reading stream:", e)
                    print("bad line:", line)

# This function starts the stream reader in a separate daemon thread. It is called once at startup after setting up the database.
def start_stream_reader():
    t = threading.Thread(target=read_stream, daemon=True)
    t.start()
    print("started stream reader thread")

# This API returns a simple health check with counts of instruments, trades and prices in the database
@app.route("/api/health")
def health():
    instrument_count = Instrument.query.count()
    trade_count = Trade.query.count()
    price_count = Price.query.count()
    #print(f"Health check: {instrument_count} instruments, {trade_count} trades, {price_count} prices")
    return jsonify({
        "status": "ok",
        "instrument_count": instrument_count,
        "trade_count": trade_count,
        "price_count": price_count
    })

# This API returns all instruments in the database as a JSON array
@app.route("/api/instruments")
def get_instrument():
    rows = Instrument.query.all()
    data = []
    for row in rows:
        data.append(row.as_dict())
    return jsonify(data)

# This API returns the latest 50 trades, ordered by event_time descending
@app.route("/api/trades/latest")
def latest_trades():
    rows = Trade.query.order_by(Trade.event_time.desc()).limit(50).all()
    data = []
    for row in rows:
        data.append(row.as_dict())
    return jsonify(data)

# This API returns the latest 50 price ticks, ordered by event_time descending
@app.route("/api/prices/latest")
def latest_prices():
    rows = Price.query.order_by(Price.event_time.desc()).limit(50).all()
    data = []
    for row in rows:
        data.append(row.as_dict())
    return jsonify(data)

# This API returns the cumulative PnL over time based on the VCR trades only. It calculates a running total of the signed notional values and returns an array of time and PnL pairs, limited to the latest 300 entries for performance reasons.
@app.route("/api/pnl")
def pnl():
    rows = (
        Trade.query
        .filter(Trade.currency == "VCR")
        .order_by(Trade.event_time.asc())
        .all()
    )
    data = []
    running_pnl = 0
    for row in rows:
        running_pnl += row.signed_notional
        data.append({
            "time": row.event_time.isoformat() if row.event_time else None,
            "pnl": round(running_pnl, 2),
            "trade_id": row.trade_id,
            "instrument_id": row.instrument_id,
            "side": row.side,
            "notional": round(row.notional, 2),
        })
    return jsonify(data[-300:])

# This route serves the main dashboard page, which will be implemented in dashboard.html
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

# The main entry point of the application. 
if __name__ == "__main__":
    with app.app_context():
        setup_database()

    start_stream_reader()

    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)