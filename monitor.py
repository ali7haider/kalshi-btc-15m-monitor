"""
Kalshi Bitcoin 15-minute market monitor.

Watches the current "BTC price up in next 15 mins?" market (series KXBTC15M).
During the final minutes before close, if the UP or DOWN side reaches the
threshold (default 87%), it records a row in results.csv. After the market
settles, the row is updated to WIN or LOSS automatically.

Run:  python3 monitor.py
Stop: Ctrl+C  (safe to restart at any time; pending rows are resolved later)
"""

import csv
import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

# ----------------------------- Settings -----------------------------------
API_URL = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXBTC15M"          # Kalshi BTC 15-minute up/down series
THRESHOLD = 87               # record when a side is at or above this %
WATCH_WINDOW_SECONDS = 6 * 60  # only watch the final 6 minutes
POLL_SECONDS = 2             # how often to check prices
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.csv")
EASTERN = ZoneInfo("America/New_York")  # Kalshi names markets in Eastern Time

COLUMNS = [
    "Date",
    "Market",
    "Side",
    "Percentage",
    "Time Detected (ET)",
    "Seconds Before Close",
    "Target Price",
    "Market Close (ET)",
    "Result",
]


# ----------------------------- Kalshi API ---------------------------------
def api_get(path, params=None):
    """GET a Kalshi public endpoint and return the JSON (no API key needed)."""
    response = requests.get(f"{API_URL}{path}", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def get_current_market():
    """Return the open KXBTC15M market that closes soonest, or None."""
    data = api_get("/markets", {"series_ticker": SERIES, "status": "open"})
    markets = data.get("markets", [])
    if not markets:
        return None
    return min(markets, key=lambda m: m["close_time"])


def get_market_result(ticker):
    """Return 'yes', 'no', or '' (not settled yet) for a market."""
    market = api_get(f"/markets/{ticker}")["market"]
    return market.get("result", "")


# ----------------------------- Helpers ------------------------------------
def parse_time(iso_text):
    """Turn Kalshi's '2026-11-11T07:00:00Z' into a timezone-aware datetime."""
    return datetime.fromisoformat(iso_text.replace("Z", "+00:00"))


def to_percent(price_dollars):
    """Convert a price like '0.9150' into 91.5 (percent). None if no price."""
    try:
        price = float(price_dollars)
    except (TypeError, ValueError):
        return None
    # 0 or 1.00 means there is no real offer on that side, so ignore it.
    if price <= 0 or price >= 1:
        return None
    return round(price * 100, 1)


def format_percent(value):
    """91.0 -> '91%', 91.5 -> '91.5%'."""
    return f"{value:g}%"


# ----------------------------- CSV storage --------------------------------
def load_rows():
    if not os.path.exists(CSV_FILE):
        return []
    with open(CSV_FILE, newline="") as f:
        return list(csv.DictReader(f))


def save_rows(rows):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


# ----------------------------- Main logic ---------------------------------
def check_market(market, rows):
    """Record a row for any side at or above the threshold. Returns True if rows changed."""
    now = datetime.now(timezone.utc)
    close_time = parse_time(market["close_time"])
    seconds_left = int((close_time - now).total_seconds())

    if seconds_left > WATCH_WINDOW_SECONDS or seconds_left < 0:
        return False

    ticker = market["ticker"]
    # YES = BTC goes UP, NO = BTC goes DOWN. The ask is the price to buy that side.
    sides = {
        "UP": to_percent(market.get("yes_ask_dollars")),
        "DOWN": to_percent(market.get("no_ask_dollars")),
    }

    changed = False
    for side, percent in sides.items():
        if percent is None or percent < THRESHOLD:
            continue
        already_recorded = any(r["Market"] == ticker and r["Side"] == side for r in rows)
        if already_recorded:
            continue

        now_et = now.astimezone(EASTERN)
        target = market.get("yes_sub_title", "").replace("Target Price:", "").strip()
        rows.append({
            "Date": now_et.strftime("%Y-%m-%d"),
            "Market": ticker,
            "Side": side,
            "Percentage": format_percent(percent),
            "Time Detected (ET)": now_et.strftime("%H:%M:%S"),
            "Seconds Before Close": seconds_left,
            "Target Price": target,
            "Market Close (ET)": close_time.astimezone(EASTERN).strftime("%Y-%m-%d %H:%M"),
            "Result": "PENDING",
        })
        print(f"  >> RECORDED {side} at {format_percent(percent)} on {ticker} "
              f"({seconds_left}s before close)")
        changed = True
    return changed


def settle_pending(rows):
    """Update PENDING rows to WIN/LOSS once their market has settled. Returns True if rows changed."""
    now = datetime.now(timezone.utc)
    changed = False
    results_cache = {}

    for row in rows:
        if row["Result"] != "PENDING":
            continue
        close_time = datetime.strptime(row["Market Close (ET)"], "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)
        if now < close_time:
            continue  # market has not closed yet

        ticker = row["Market"]
        if ticker not in results_cache:
            results_cache[ticker] = get_market_result(ticker)
        result = results_cache[ticker]
        if result not in ("yes", "no"):
            continue  # closed but not settled yet, try again later

        winning_side = "UP" if result == "yes" else "DOWN"
        row["Result"] = "WIN" if row["Side"] == winning_side else "LOSS"
        print(f"  >> SETTLED {ticker}: {row['Side']} -> {row['Result']}")
        changed = True
    return changed


def main():
    print(f"Kalshi BTC 15-min monitor | threshold {THRESHOLD}% | "
          f"final {WATCH_WINDOW_SECONDS // 60} min | saving to {CSV_FILE}")
    print("Press Ctrl+C to stop.\n")

    rows = load_rows()
    save_rows(rows)  # creates results.csv with headers if it doesn't exist yet
    last_status = ""

    while True:
        try:
            changed = settle_pending(rows)

            market = get_current_market()
            if market:
                changed = check_market(market, rows) or changed

                # Print a short status line whenever the minute changes.
                seconds_left = int((parse_time(market["close_time"]) - datetime.now(timezone.utc)).total_seconds())
                up = to_percent(market.get("yes_ask_dollars"))
                down = to_percent(market.get("no_ask_dollars"))
                status = (f"{datetime.now(EASTERN):%H:%M} ET | {market['ticker']} | "
                          f"UP {up}% DOWN {down}% | {seconds_left // 60}m left")
                if status[:5] != last_status[:5]:
                    print(status)
                    last_status = status
            if changed:
                save_rows(rows)

        except requests.RequestException as error:
            print(f"Network error (will retry): {error}")
        except KeyboardInterrupt:
            raise
        except Exception as error:  # keep running no matter what
            print(f"Unexpected error (will retry): {error}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Your data is saved in results.csv")
