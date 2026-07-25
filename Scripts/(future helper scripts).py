import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------
# Alpaca
# -----------------------

API_KEY = os.environ["ALPACA_API_KEY"]
API_SECRET = os.environ["ALPACA_API_SECRET"]

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"

# -----------------------
# Google Sheets
# -----------------------

SHEET_NAME = "Day Trading Sheet"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDS_FILE = os.environ.get(
    "GOOGLE_CREDS_FILE",
    "data/day-trading-scr-32d7db89c6b8.json",
)

# -----------------------
# Trading
# -----------------------

TICKERS = [
    "BBAI",
    "OPEN",
    "SOUN",
    "SOFI",
    "RIVN",
    "PLTR",
]

ATR_MULTIPLIER = 0.25

STOP_BUFFER = 0.05