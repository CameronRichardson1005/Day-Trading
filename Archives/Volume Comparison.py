import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["ALPACA_API_KEY"]
API_SECRET = os.environ["ALPACA_API_SECRET"]

HEADERS = {
    "accept": "application/json",
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
}

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"

CURRENT_TICKERS = ["BBAI", "OPEN", "SOUN"]
CANDIDATE_TICKERS = ["SOXL", "AMD", "SNAP", "PINS", "LYFT", "UBER", "AI", "IONQ", "RGTI","MRNA", "NVAX", "SAVA", "BNTX", "INO", "OCGN", "VXRT"]

ALL_TICKERS = CURRENT_TICKERS + CANDIDATE_TICKERS

LOOKBACK_DAYS = 30


def get_stats(symbol, lookback_days=LOOKBACK_DAYS):
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=lookback_days * 2)  # buffer for weekends/holidays

    params = {
        "symbols": symbol,
        "timeframe": "1Day",
        "start": start_date.strftime("%Y-%m-%d") + "T00:00:00Z",
        "end": end_date.strftime("%Y-%m-%d") + "T23:59:59Z",
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": lookback_days * 2,
        "sort": "desc"
    }

    data = requests.get(BASE_URL, headers=HEADERS, params=params).json()
    bars = data.get("bars", {}).get(symbol, [])

    if not bars:
        return None

    bars = bars[:lookback_days]

    avg_volume = sum(b["v"] for b in bars) / len(bars)
    avg_price = sum(b["c"] for b in bars) / len(bars)
    avg_range = sum(b["h"] - b["l"] for b in bars) / len(bars)
    avg_range_pct = (avg_range / avg_price) * 100 if avg_price else 0

    return {
        "avg_volume": round(avg_volume),
        "avg_price": round(avg_price, 2),
        "avg_range": round(avg_range, 3),
        "avg_range_pct": round(avg_range_pct, 2),
    }


print(f"{'Symbol':<8}{'Avg Volume':<15}{'Avg Price':<12}{'Avg Range ($)':<15}{'Avg Range (%)':<15}{'Category'}")
print("-" * 85)

results = []
for symbol in ALL_TICKERS:
    stats = get_stats(symbol)
    category = "Current" if symbol in CURRENT_TICKERS else "Candidate"
    results.append((symbol, stats, category))

# Sort by volume, highest first (None values sink to the bottom)
results.sort(key=lambda x: (x[1] is not None, x[1]["avg_volume"] if x[1] else 0), reverse=True)

for symbol, stats, category in results:
    if stats is None:
        print(f"{symbol:<8}{'No data':<15}{'':<12}{'':<15}{'':<15}{category}")
    else:
        print(
            f"{symbol:<8}{stats['avg_volume']:<15,}{stats['avg_price']:<12}"
            f"{stats['avg_range']:<15}{stats['avg_range_pct']:<15}{category}"
        )