import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=True)


API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_API_SECRET")

if not API_KEY:
    raise RuntimeError("ALPACA_API_KEY was not found in the .env file.")

if not API_SECRET:
    raise RuntimeError("ALPACA_API_SECRET was not found in the .env file.")


BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"

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

SHEET_NAME = "Day Trading Sheet"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDS_FILE = os.getenv(
    "GOOGLE_CREDS_FILE",
    str(
        PROJECT_ROOT
        / "Scripts"
        / "data"
        / "day-trading-scr-32d7db89c6b8.json"

    ),
)
