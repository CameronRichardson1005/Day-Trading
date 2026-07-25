import requests
import time
import gspread
from google.oauth2.service_account import Credentials
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
TICKERS = ["BBAI", "OPEN", "SOUN","PLTR","SOFI","RIVN","AMC","PLUG","MARA"]

TARGET_TRADING_DAYS = 21
MAX_CALENDAR_LOOKBACK = 45
REQUEST_DELAY = 0.15

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "/Archives/day-trading-scr-32d7db89c6b8.json"
SHEET_NAME = "Day Trading Sheet"
WORKSHEET_NAME = "Low Projections"

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open(SHEET_NAME)

try:
    projections_ws = sh.worksheet(WORKSHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    projections_ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=100, cols=12)

COLUMNS = [
    "Date", "Symbol", "Days Sampled", "Avg Extension %", "Median Extension %",
    "Worst Case Extension %", "Today's Opening Low", "Projected Low (Avg)",
    "Projected Low (Median)", "Projected Low (Worst Case)"
]

existing_values = projections_ws.get_all_values()
if not existing_values or existing_values[0] != COLUMNS:
    projections_ws.update(values=[COLUMNS], range_name="A1")
    existing_values = projections_ws.get_all_values()


def get_minute_bars_for_day(symbol, date_str):
    params = {
        "symbols": symbol,
        "timeframe": "1Min",
        "start": f"{date_str}T13:30:00Z",
        "end": f"{date_str}T20:00:00Z",
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": 500,
        "sort": "asc"
    }
    response = requests.get(BASE_URL, headers=HEADERS, params=params)
    print(f"{symbol} {date_str} - status: {response.status_code} - raw: {response.text[:300]}", flush=True)
    data = response.json()
    time.sleep(REQUEST_DELAY)
    return data.get("bars", {}).get(symbol, [])


def analyze_historical_low_extension(symbol, end_date_str, target_days=TARGET_TRADING_DAYS):
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    extensions = []
    checked_days = 0
    day_offset = 1

    while checked_days < target_days and day_offset <= MAX_CALENDAR_LOOKBACK:
        check_date = end_date - timedelta(days=day_offset)
        date_str = check_date.strftime("%Y-%m-%d")
        day_offset += 1

        bars = get_minute_bars_for_day(symbol, date_str)
        if len(bars) < 20:
            continue

        opening_bars = [b for b in bars if b["t"] <= f"{date_str}T13:45:00Z"]
        rest_of_day_bars = [b for b in bars if b["t"] > f"{date_str}T13:45:00Z"]

        if not opening_bars or not rest_of_day_bars:
            continue

        opening_low = min(b["l"] for b in opening_bars)
        rest_of_day_low = min(b["l"] for b in rest_of_day_bars)

        if opening_low == 0:
            continue

        extension_pct = max(0, (opening_low - rest_of_day_low) / opening_low * 100)
        extensions.append(extension_pct)
        checked_days += 1

    return extensions


today_str = datetime.now().strftime("%Y-%m-%d")

# Find or prepare today's row for each symbol (overwrite-on-rerun, same pattern as your other scripts)
symbol_rows = {}
for i, row in enumerate(existing_values[1:], start=2):
    if len(row) >= 2 and row[0] == today_str and row[1] in TICKERS:
        symbol_rows[row[1]] = i

missing_symbols = [s for s in TICKERS if s not in symbol_rows]
if missing_symbols:
    next_row = len(existing_values) + 1
    new_rows = []
    for symbol in missing_symbols:
        symbol_rows[symbol] = next_row
        new_rows.append([today_str, symbol, "", "", "", "", "", "", "", ""])
        next_row += 1

    projections_ws.update(
        values=new_rows,
        range_name=f"A{len(existing_values) + 1}:J{len(existing_values) + len(new_rows)}"
    )

for symbol in TICKERS:
    print(f"\n=== {symbol} ===")
    print(f"Analyzing last {TARGET_TRADING_DAYS} trading days for {symbol}...")

    extensions = analyze_historical_low_extension(symbol, today_str)

    if not extensions:
        print("Not enough historical data to project.")
        row = symbol_rows[symbol]
        projections_ws.update(values=[["Not enough data", "", "", "", "", "", ""]], range_name=f"C{row}:I{row}")
        continue

    avg_extension = sum(extensions) / len(extensions)
    sorted_ext = sorted(extensions)
    median_extension = sorted_ext[len(sorted_ext) // 2]
    worst_case = max(extensions)

    print(f"Sampled {len(extensions)} valid trading days")
    print(f"Average extension below opening low: {round(avg_extension, 3)}%")
    print(f"Median extension: {round(median_extension, 3)}%")
    print(f"Worst-case (max) extension seen: {round(worst_case, 3)}%")

    # Try to get today's actual opening low, if the market's been open
    params = {
        "symbols": symbol,
        "timeframe": "15Min",
        "start": f"{today_str}T13:30:00Z",
        "end": f"{today_str}T13:45:00Z",
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": 1
    }
    data = requests.get(BASE_URL, headers=HEADERS, params=params).json()
    bars = data.get("bars", {}).get(symbol, [])

    if bars:
        current_opening_low = bars[0]["l"]
        projected_avg = round(current_opening_low * (1 - avg_extension / 100), 4)
        projected_median = round(current_opening_low * (1 - median_extension / 100), 4)
        projected_worst = round(current_opening_low * (1 - worst_case / 100), 4)
        print(f"Today's opening low: {current_opening_low}")
        print(f"Projected low (avg case): {projected_avg}")
        print(f"Projected low (median case): {projected_median}")
        print(f"Projected low (worst case): {projected_worst}")
    else:
        current_opening_low = "N/A"
        projected_avg = ""
        projected_median = ""
        projected_worst = ""
        print("(No opening bar today yet — historical percentages only)")

    row = symbol_rows[symbol]
    projections_ws.update(values=[[
        len(extensions),
        round(avg_extension, 3),
        round(median_extension, 3),
        round(worst_case, 3),
        current_opening_low,
        projected_avg,
        projected_median,
        projected_worst
    ]], range_name=f"C{row}:J{row}")

print("\nLow projections updated in Google Sheet.")