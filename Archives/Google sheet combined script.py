import os
import requests
import time
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor


load_dotenv()

API_KEY = os.environ["ALPACA_API_KEY"]
API_SECRET = os.environ["ALPACA_API_SECRET"]

HEADERS = {
    "accept": "application/json",
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
}

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"
TICKERS = ["BBAI", "OPEN", "SOUN", "SOFI", "RIVN"]
SYMBOLS_CSV = ",".join(TICKERS)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CREDS_FILE = os.environ.get(
    "GOOGLE_CREDS_FILE",
    "/day-trading-scr-32d7db89c6b8.json",
)
SHEET_NAME = "Day Trading Sheet"

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open(SHEET_NAME)


def get_or_create_worksheet(title, rows=100, cols=20):
    try:
        return sh.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


oneminute_ws = get_or_create_worksheet("1 minute intervals")
invest_ws = get_or_create_worksheet("Invest")
orders_ws = get_or_create_worksheet("Orders", cols=5)
summary_ws = get_or_create_worksheet("Summary", cols=10)


WHITE = {"red": 1, "green": 1, "blue": 1}
LIGHT_BLUE = {"red": 0.68, "green": 0.85, "blue": 0.9}
LIGHT_RED = {"red": 1, "green": 0.75, "blue": 0.75}
LIGHT_GREEN = {"red": 0.78, "green": 0.93, "blue": 0.78}

today = datetime.now()
today_str = today.strftime("%Y-%m-%d")



def call_with_retries(func, *args, max_retries=3, backoff_seconds=2, label="request", **kwargs):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt == max_retries:
                break
            wait = backoff_seconds * attempt
            print(f"{label} failed (attempt {attempt}/{max_retries}): {e} — retrying in {wait}s", flush=True)
            time.sleep(wait)
    raise last_error


# ---------------------------------------------------------------------------
# Market data helpers — now request ALL symbols in a single HTTP call.
# ---------------------------------------------------------------------------
def get_1min_bars_all(symbols_csv, start_iso, end_iso):
    """One API call for every ticker's 1-min bar in this window."""
    params = {
        "symbols": symbols_csv,
        "timeframe": "1Min",
        "start": start_iso,
        "end": end_iso,
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": 1000,
        "sort": "desc",
    }
    response = call_with_retries(
        requests.get, BASE_URL, headers=HEADERS, params=params, label="1-min bars fetch"
    )
    print(f"batch bars - status: {response.status_code} - body: {response.text}", flush=True)
    data = response.json()
    bars_by_symbol = data.get("bars", {})
    return {symbol: (bars_by_symbol.get(symbol) or [None])[0] for symbol in TICKERS}


def get_opening_15min_bars_all(symbols_csv, date_str):
    params = {
        "symbols": symbols_csv,
        "timeframe": "15Min",
        "start": f"{date_str}T13:30:00Z",
        "end": f"{date_str}T13:45:00Z",
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": 1000,
    }
    print(rows_to_append)

    response = call_with_retries(
        requests.get,
        BASE_URL,
        headers=HEADERS,
        params=params,
        label="opening 15-min bars fetch",
    )

    data = response.json()

    print("\n===== 15 MINUTE RESPONSE =====")
    print(data)

    bars_by_symbol = data.get("bars", {})

    print("15-minute symbols returned:", list(bars_by_symbol.keys()))

    return {
        symbol: (bars_by_symbol.get(symbol) or [None])[0]
        for symbol in TICKERS
    }

def get_previous_day_ranges_all(symbols_csv, date_str):
    """One API call for all symbols' daily bars, then compute ATR per symbol."""
    end_date = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
    start_date = end_date - timedelta(days=180)


    params = {
        "symbols": symbols_csv,
        "timeframe": "1Day",
        "start": start_date.strftime("%Y-%m-%d") + "T00:00:00Z",
        "end": end_date.strftime("%Y-%m-%d") + "T23:59:59Z",
        "adjustment": "raw",
        "feed": "iex",
        "currency": "usd",
        "limit": 1000,
        "sort": "desc",
    }

    response = call_with_retries(
        requests.get, BASE_URL, headers=HEADERS, params=params, label="ATR daily bars fetch"
    )
    data = response.json()
    bars_by_symbol = data.get("bars", {})

    print("\n===== DAILY ATR RESPONSE =====")
    print("Daily ATR symbols:", list(bars_by_symbol.keys()))

    results = {}
    for symbol in TICKERS:
        bars = bars_by_symbol.get(symbol, [])
        if len(bars) < 15:
            results[symbol] = None
            continue

        bars = list(bars)
        bars.reverse()
        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i]["h"]
            low = bars[i]["l"]
            prev_close = bars[i - 1]["c"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        atr = sum(true_ranges[:14]) / 14
        for true_range in true_ranges[14:]:
            atr = ((atr * 13) + true_range) / 14

        results[symbol] = atr

    return results


ONEMIN_COLUMNS = ["Date", "Symbol", "Running High", "Running Low", "Last Update Time", "Candle Color"]

existing_1min = oneminute_ws.get_all_values()
if not existing_1min or existing_1min[0] != ONEMIN_COLUMNS:
    oneminute_ws.update(values=[ONEMIN_COLUMNS], range_name="A1")
    existing_1min = oneminute_ws.get_all_values()

symbol_rows = {}
for i, row in enumerate(existing_1min[1:], start=2):
    if len(row) >= 2 and row[0] == today_str and row[1] in TICKERS:
        symbol_rows[row[1]] = i

missing_symbols = [s for s in TICKERS if s not in symbol_rows]

if missing_symbols:
    next_row = len(existing_1min) + 1
    new_rows = []
    for symbol in missing_symbols:
        symbol_rows[symbol] = next_row
        new_rows.append([today_str, symbol, "", "", "", ""])
        next_row += 1

    oneminute_ws.update(
        values=new_rows,
        range_name=f"A{len(existing_1min) + 1}:F{len(existing_1min) + len(new_rows)}",
    )

running_high = {symbol: None for symbol in TICKERS}
running_low = {symbol: None for symbol in TICKERS}

new_high_count = {symbol: 0 for symbol in TICKERS}
new_low_count = {symbol: 0 for symbol in TICKERS}
green_minutes = {symbol: 0 for symbol in TICKERS}
red_minutes = {symbol: 0 for symbol in TICKERS}

window_start = datetime.strptime(f"{today_str}T13:30:00", "%Y-%m-%dT%H:%M:%S")
window_end = datetime.strptime(f"{today_str}T13:45:00", "%Y-%m-%dT%H:%M:%S")
current_minute = window_start

# Column indices (0-based) within the sheet for building batch requests
sheet_id = oneminute_ws.id
COL_C, COL_D, COL_E, COL_F = 2, 3, 4, 5  # 0-based: C,D,E,F

while current_minute <= window_end:
    minute_start_iso = current_minute.strftime("%Y-%m-%dT%H:%M:%SZ")
    minute_end_iso = (current_minute + timedelta(seconds=59)).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_label = current_minute.strftime("%H:%M")

    try:
        bars = get_1min_bars_all(SYMBOLS_CSV, minute_start_iso, minute_end_iso)
    except Exception as e:
        print(f"ERROR fetching batch bars at {current_minute}: {e}", flush=True)
        bars = {symbol: None for symbol in TICKERS}

    value_updates = []   # for one batched values write
    format_requests = []  # for one batched formatting write (raw Sheets API requests)

    for symbol in TICKERS:
        bar = bars.get(symbol)
        if bar is None:
            print(f"{symbol} - no bar data for {time_label}", flush=True)
            continue

        m_open = bar["o"]
        m_close = bar["c"]
        m_high = bar["h"]
        m_low = bar["l"]

        candle_color = "GREEN" if m_close > m_open else "RED"
        if candle_color == "GREEN":
            green_minutes[symbol] += 1
        else:
            red_minutes[symbol] += 1

        new_high = False
        new_low = False

        if running_high[symbol] is None or m_high > running_high[symbol]:
            running_high[symbol] = m_high
            new_high = True
            new_high_count[symbol] += 1

        if running_low[symbol] is None or m_low < running_low[symbol]:
            running_low[symbol] = m_low
            new_low = True
            new_low_count[symbol] += 1

        row = symbol_rows[symbol]
        row_idx0 = row - 1  # 0-based for API requests

        value_updates.append({
            "range": f"C{row}:F{row}",
            "values": [[
                round(running_high[symbol], 4),
                round(running_low[symbol], 4),
                time_label,
                candle_color,
            ]],
        })

        def cell_format_request(col0, color):
            return {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_idx0,
                        "endRowIndex": row_idx0 + 1,
                        "startColumnIndex": col0,
                        "endColumnIndex": col0 + 1,
                    },
                    "cell": {"userEnteredFormat": {"backgroundColor": color}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }

        format_requests.append(cell_format_request(COL_C, LIGHT_BLUE if new_high else WHITE))
        format_requests.append(cell_format_request(COL_D, LIGHT_RED if new_low else WHITE))
        format_requests.append(cell_format_request(COL_F, LIGHT_GREEN if candle_color == "GREEN" else WHITE))

    # One Sheets API call for all symbols' values this minute
    if value_updates:
        try:
            call_with_retries(
                oneminute_ws.batch_update, value_updates, label=f"Sheets values write ({time_label})"
            )
        except Exception as e:
            print(f"ERROR writing batched values at {current_minute}: {e}", flush=True)

    # One Sheets API call for all symbols' formatting this minute
    if format_requests:
        try:
            call_with_retries(
                sh.batch_update, {"requests": format_requests}, label=f"Sheets formatting write ({time_label})"
            )
        except Exception as e:
            print(f"ERROR writing batched formatting at {current_minute}: {e}", flush=True)

    print(f"1-min update logged for {time_label}", flush=True)

    # Fixed: advance exactly one minute and sleep once per minute, no
    # double-advance / double-sleep.
    current_minute += timedelta(minutes=1)
    if current_minute <= window_end:
        time.sleep(60)

print("Finished 1-minute tracking window.", flush=True)


INVEST_COLUMNS = [
    "Date", "Symbol", "Open", "High", "Low", "Close",
    "Prev Day Range (ATR)", "ATR x 0.25", "Candle Range",
    "Manipulation Candle", "Red Candle", "Signal",
    "Limit Buy", "Limit Sell", "Stop Loss", "Trading Stop Loss", "Proximity to High/Low",
]

existing_invest = invest_ws.get_all_values()
if not existing_invest or existing_invest[0] != INVEST_COLUMNS:
    invest_ws.update(values=[INVEST_COLUMNS], range_name="A1")

ORDER_COLUMNS = ["Date", "Symbol", "Limit Buy", "Limit Sell", "Trading Stop Loss"]
existing_orders = orders_ws.get_all_values()
if not existing_orders or existing_orders[0] != ORDER_COLUMNS:
    orders_ws.update(values=[ORDER_COLUMNS], range_name="A1")

rows_to_append = []
orders_to_append = []

total_signals = 0
invest_signals = 0
manipulation_count = 0
red_candle_count = 0

# Single batched calls instead of one request per symbol
opening_bars = get_opening_15min_bars_all(SYMBOLS_CSV, today_str)
atrs = get_previous_day_ranges_all(SYMBOLS_CSV, today_str)


for symbol in TICKERS:
    opening_bar = opening_bars.get(symbol)
    atr = atrs.get(symbol)

    print(f"\n----- {symbol} -----")
    print("Opening Bar:", opening_bar)
    print("ATR:", atr)
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

    signal = (
        "INVEST"
        if manipulation_final and is_red
        else "NO INVEST"
    )
    print(
        f"Signal={signal}, "
        f"Manipulation={manipulation_final}, "
        f"Red={is_red}")
    print(
        symbol,
        "Manipulation:", manipulation_final,
        "Red:", is_red,
        "Signal:", signal
    )

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
    print(symbol, signal)

    total_signals += 1
    if signal == "INVEST":
        invest_signals += 1
        orders_to_append.append([
            today_str, symbol, round(limit_buy, 4), round(limit_sell, 4), round(trading_stop_loss, 4)
        ])
    if is_manipulation:
        manipulation_count += 1
    if is_red:
        red_candle_count += 1

print("\n===== ORDERS =====")
print(orders_to_append)

call_with_retries(invest_ws.append_rows, rows_to_append, label="Invest sheet append")

print("Orders to append:")
print(orders_to_append)

print("\n===== ORDERS =====")
print("Orders to append:")
print(orders_to_append)

if orders_to_append:
    print("Writing Orders sheet...")

    call_with_retries(
        orders_ws.append_rows,
        orders_to_append,
        label="Orders sheet append"
    )

    print("Orders sheet written.")
else:
    print("No orders generated.")
print("Data appended to Google Sheet.", flush=True)


SUMMARY_COLUMNS = [
    "Date", "Tickers Checked", "INVEST Signals", "Manipulation Candles",
    "Red Candles (15min)", "Total New Highs (1min)", "Total New Lows (1min)",
    "Green Minutes", "Red Minutes",
]

existing_summary = summary_ws.get_all_values()
if not existing_summary or existing_summary[0] != SUMMARY_COLUMNS:
    summary_ws.update(values=[SUMMARY_COLUMNS], range_name="A1")
    existing_summary = summary_ws.get_all_values()

summary_row_num = None
for i, row in enumerate(existing_summary[1:], start=2):
    if len(row) >= 1 and row[0] == today_str:
        summary_row_num = i
        break

total_new_highs = sum(new_high_count.values())
total_new_lows = sum(new_low_count.values())
total_green = sum(green_minutes.values())
total_red = sum(red_minutes.values())

summary_row = [
    today_str, len(TICKERS), invest_signals, manipulation_count,
    red_candle_count, total_new_highs, total_new_lows, total_green, total_red,
]

if summary_row_num:
    call_with_retries(
        summary_ws.update, values=[summary_row], range_name=f"A{summary_row_num}:I{summary_row_num}",
        label="Summary sheet update",
    )
else:
    call_with_retries(summary_ws.append_row, summary_row, label="Summary sheet append")

print("Summary updated.", flush=True)