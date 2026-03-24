"""
CSV trade reporting logic.
"""
import csv
import os
import logging
from datetime import datetime

log = logging.getLogger("polybot")

CSV_PATH = "trades.csv"

FIELDNAMES = [
    "timestamp_utc",
    "current_market_id",
    "next_market_id",
    "signal_side",
    "selected_odds",
    "execution_price",
    "opposing_odds",
    "price_to_beat",
    "btc_price",
    "price_gap",
    "latency_ms",
    "order_size",
    "success",
    "status",
    "order_id",
    "pnl" # Left blank to be filled manually or by PNL loop later
]

def init_csv():
    """Initializes the CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
            log.info("Initialized %s", CSV_PATH)
        except Exception as e:
            log.error("Failed to initialize CSV logger: %s", e)

def log_trade(trade_data: dict):
    """Appends a trade snapshot to the CSV logger."""
    row = {key: trade_data.get(key, "") for key in FIELDNAMES}
    
    try:
        with open(CSV_PATH, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerow(row)
    except Exception as e:
        log.error("Failed to write to CSV logger: %s", e)
