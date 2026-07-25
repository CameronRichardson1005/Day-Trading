import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

import requests
import gspread
from google.oauth2.service_account import Credentials
import time
from datetime import datetime, timedelta


API_KEY = os.environ["ALPACA_API_KEY"]
API_SECRET = os.environ["ALPACA_API_SECRET"]

HEADERS = {
    "accept": "application/json",
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
}

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"
TICKERS = ["BBAI", "OPEN", "SOUN"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "/day-trading-scr-32d7db89c6b8.json"
SHEET_NAME = "Day Trading Sheet"
WORKSHEET_NAME = "Invest"
ORDERS_WORKSHEET = "Orders"

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

sh = gc.open(SHEET_NAME)

try:
    worksheet = sh.worksheet(WORKSHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    worksheet = sh.add_worksheet(title=WORKSHEET_NAME, rows=100, cols=20)
try:
    orders_ws = sh.worksheet(ORDERS_WORKSHEET)
except gspread.exceptions.WorksheetNotFound:
    orders_ws = sh.add_worksheet(title=ORDERS_WORKSHEET, rows=100, cols=5)

ORDER_COLUMNS = [
    "Date",
    "Symbol",
    "Limit Buy",
    "Limit Sell",
    "Trading Stop Loss"
]

existing = orders_ws.get_all_values()
if not existing or existing[0] != ORDER_COLUMNS:
    orders_ws.clear()
    orders_ws.update("A1", [ORDER_COLUMNS])
COLUMNS = [
    "Date", "Symbol", "Open", "High", "Low", "Close",
    "Prev Day Range (ATR)", "ATR x 0.25", "Candle Range",
    "Manipulation Candle", "Red Candle", "Signal",
    "Limit Buy", "Limit Sell", "Stop Loss", "Trading Stop Loss", "Proximity to High/Low"
]

existing_values = worksheet.get_all_values()
if not existing_values or existing_values[0] != COLUMNS:
    worksheet.update(values=[COLUMNS], range_name="A1")
    existing_values = worksheet.get_all_values()


def get_opening_15min_bar(symbol, date_str):
    params = {
        "symbols": symbol,
        "timeframe": "15Min",
        "start": f"{date_str}T13:30:00Z",
        "end": f"{date_str}T13:45:00Z",
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": 1
    }
    data = requests.get(BASE_URL, headers=HEADERS, params=params).json()
    bars = data.get("bars", {}).get(symbol, [])
    return bars[0] if bars else None


def get_previous_day_range(symbol, date_str):
    end_date = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
    start_date = end_date - timedelta(days=180)

    params = {
        "symbols": symbol,
        "timeframe": "1Day",
        "start": start_date.strftime("%Y-%m-%d") + "T00:00:00Z",
        "end": end_date.strftime("%Y-%m-%d") + "T23:59:59Z",
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": 100,
        "sort": "desc"
    }

    data = requests.get(BASE_URL, headers=HEADERS, params=params).json()
    bars = data.get("bars", {}).get(symbol, [])

    if len(bars) < 15:
        return None

    bars.reverse()

    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i]["h"]
        low = bars[i]["l"]
        prev_close = bars[i - 1]["c"]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)

    atr = sum(true_ranges[:14]) / 14
    for true_range in true_ranges[14:]:
        atr = ((atr * 13) + true_range) / 14

    return atr


today = datetime.now()
today_str = today.strftime("%Y-%m-%d")

rows_to_append = []
orders_to_append = []

for symbol in TICKERS:
    opening_bar = get_opening_15min_bar(symbol, today_str)
    atr = get_previous_day_range(symbol, today_str)

    print(f"{symbol} - opening_bar: {opening_bar}")
    print(f"{symbol} - atr: {atr}")

    if opening_bar is None or atr is None:
        rows_to_append.append([today_str, symbol, "No data", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
        continue


    high = opening_bar["h"]
    low = opening_bar["l"]
    open_price = opening_bar["o"]
    close_price = opening_bar["c"]

    candle_range = high - low
    atr_threshold = atr * 0.25
    is_manipulation = candle_range > atr_threshold
    is_within_margin = (atr_threshold - candle_range) <= 0.005
    is_red = open_price > close_price
    manipulation_final = is_manipulation or is_within_margin

    limit_buy = low
    limit_sell = low + ((high - low) * 0.382)
    stop_loss = limit_buy - ((limit_sell - limit_buy) / 2)

    stop_loss_is_too_close = (limit_buy - 0.05) < stop_loss
    if stop_loss_is_too_close:
        stop_loss -= 0.05
    trading_stop_loss = stop_loss - 0.05

    if not manipulation_final:
        signal = "NO INVEST"
    else:
        signal = "INVEST" if is_red else "NO INVEST"

    dist_from_high = high - close_price
    dist_from_low = close_price - low
    if dist_from_low <= dist_from_high:
        proximity = f"{round(dist_from_low * 100, 1)}¢ from Low"
    else:
        proximity = f"{round(dist_from_high * 100, 1)}¢ from High"

    rows_to_append.append([
        today_str, symbol, open_price, high, low, close_price,
        round(atr, 4), round(atr_threshold, 4), round(candle_range, 4),
        "YES" if is_manipulation else "NO",
        "YES" if is_red else "NO",
        signal,
        round(limit_buy, 4), round(limit_sell, 4), round(stop_loss, 4), round(trading_stop_loss, 4),
        proximity,
    ])
    if signal == "INVEST":
        orders_to_append.append([
            today_str, symbol, round(limit_buy, 4), round(limit_sell, 4), round(trading_stop_loss, 4)
    ])

worksheet.append_rows(rows_to_append),

if orders_to_append:
    orders_ws.append_rows(orders_to_append),

print("Data appended to Google Sheet.")
