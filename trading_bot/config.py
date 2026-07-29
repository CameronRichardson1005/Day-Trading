import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=False)


API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_API_SECRET")

if not API_KEY:
    raise RuntimeError("ALPACA_API_KEY was not found in the .env file.")

if not API_SECRET:
    raise RuntimeError("ALPACA_API_SECRET was not found in the .env file.")


BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"

ALPACA_DATA_FEED = os.getenv(
    "ALPACA_DATA_FEED",
    "sip",
).strip().lower()

if ALPACA_DATA_FEED not in {"iex", "sip"}:
    raise RuntimeError(
        "ALPACA_DATA_FEED must be 'iex' or 'sip'."
    )

MARKET_DATA_FEED = ALPACA_DATA_FEED

TICKERS = [
    "BBAI",
    "OPEN",
    "SOUN",
    "SOFI",
    "RIVN",
    "PLTR",
]

CANDIDATE_TICKERS = [
    "SNAP",
    "UBER",
    "PINS",
    "RGTI",
    "SOXL",
    "LYFT",
]

ATR_MULTIPLIER = 0.25
STOP_BUFFER = 0.05

DASHBOARD_URL = os.getenv(
    "DASHBOARD_URL",
    (
        "https://trading-bot-dashboard."
        "icy-grebe-0605.chatgpt.site"
        "/api/sessions/latest"
    ),
).strip()

DASHBOARD_INGEST_KEY = os.getenv(
    "DASHBOARD_INGEST_KEY",
    "",
).strip()

DASHBOARD_SITE_TOKEN = os.getenv(
    "DASHBOARD_SITE_TOKEN",
    "",
).strip()

DASHBOARD_REQUEST_TIMEOUT = (5, 15)

SPREADSHEET_ID = os.getenv(
    "GOOGLE_SPREADSHEET_ID",
    "1fe4SD1jGvZ9bVudcFc--o8fwlHoiAxZSYeMUypNVFOQ",
).strip()

if not SPREADSHEET_ID:
    raise RuntimeError(
        "GOOGLE_SPREADSHEET_ID cannot be empty."
    )

SHEETS_REQUEST_TIMEOUT = (10, 20)

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

# Webull preview-only integration.
WEBULL_APP_KEY = os.getenv(
    "WEBULL_APP_KEY",
    "",
).strip()

WEBULL_APP_SECRET = os.getenv(
    "WEBULL_APP_SECRET",
    "",
).strip()

WEBULL_PREVIEW_ENABLED = (
    os.getenv(
        "WEBULL_PREVIEW_ENABLED",
        "false",
    ).strip().lower()
    in {"1", "true", "yes", "on"}
)

WEBULL_PREVIEW_RISK_DOLLARS = float(
    os.getenv(
        "WEBULL_PREVIEW_RISK_DOLLARS",
        "25",
    )
)

WEBULL_PREVIEW_MAX_SHARES = int(
    os.getenv(
        "WEBULL_PREVIEW_MAX_SHARES",
        "1000",
    )
)

if WEBULL_PREVIEW_RISK_DOLLARS <= 0:
    raise RuntimeError(
        "WEBULL_PREVIEW_RISK_DOLLARS must be positive."
    )

if WEBULL_PREVIEW_MAX_SHARES <= 0:
    raise RuntimeError(
        "WEBULL_PREVIEW_MAX_SHARES must be positive."
    )
