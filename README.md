# Professional Day Trading Bot

A modular paper-trading research platform that collects market data, evaluates trading strategies, tracks hypothetical outcomes, and publishes results to a live Cloudflare dashboard.

The project is designed for **research, replay, and paper analysis only**. It does not submit live brokerage orders.

## Live Dashboard

**Trading Desk:**  
https://cameron-trading-desk.cameron-richardson.workers.dev/

The dashboard displays:

- Current and historical strategy sessions
- Opening-window data quality
- INVEST / NO INVEST decisions
- Fibonacci strategy levels
- Hypothetical trade outcomes
- Session comparison and history
- Strategy performance summaries
- Scanner reliability and audit information

## Project Overview

The system currently uses a Fibonacci retracement strategy as its active paper-trading workflow.

Each session:

1. Selects symbols using historical opening-bar reliability.
2. Downloads one-minute Alpaca market data.
3. Builds the 09:30–09:44 New York opening window.
4. Evaluates Fibonacci pullback and confirmation rules.
5. Calculates hypothetical entry, target, stop, and outcome data.
6. Publishes read-only session data to the Cloudflare Trading Desk.
7. Optionally writes dedicated paper results to Google Sheets.

The original manipulation strategy remains preserved for historical replay, comparison, testing, and audit purposes, but it is no longer used for active INVEST routing.

## Architecture

```text
Alpaca Market Data
        |
        v
Symbol Reliability Scanner
        |
        v
One-Minute Opening Tracker
        |
        v
Active Fibonacci Strategy
        |
        +----------------------+
        |                      |
        v                      v
Historical / Paper Outcomes   Google Sheets
        |
        v
Dashboard Payload Exporter
        |
        v
Cloudflare Worker API
        |
        v
Cloudflare D1 Database
        |
        v
Trading Desk Web Application
```

### Main Python Components

- `main.py` — command-line entry point and workflow routing.
- `TradingBot` — coordinates scanner, replay, live-paper, backfill, dashboard, and strategy workflows.
- `AlpacaClient` — retrieves historical and one-minute market data.
- `HistoricalReplay` — reconstructs market sessions and calculates hypothetical outcomes.
- `FibonacciStrategy` — evaluates impulse, pullback, retracement, confirmation, target, and stop rules.
- `DashboardExporter` — builds validated dashboard payloads and publishes them to Cloudflare.
- `SheetsClient` — writes dedicated paper-trading results to Google Sheets.

## Safety Controls

This project contains multiple safeguards intended to prevent accidental live trading:

- **Paper analysis only**
- No live brokerage order submission
- No automatic order replacement or cancellation
- No Webull order submission
- Historical backfills are dashboard-only
- Replay mode disables Sheets and trading workflows
- Dashboard uploads are authenticated
- Production and paper workflows are separated
- Active strategy routing is controlled through configuration
- Historical sessions are labeled separately from forward-paper sessions
- Incomplete market-data sessions are preserved and flagged rather than repaired with fabricated bars

The dashboard and logs clearly display:

```text
PAPER ONLY — NOT SUBMITTED
```

## Technology Stack

### Backend and Trading Engine

- Python 3
- Alpaca Market Data API
- CSV reporting
- Google Sheets API
- Environment-based configuration
- Pytest
- ZoneInfo for New York and UTC session handling

### Dashboard

- TypeScript
- Cloudflare Workers
- Cloudflare D1
- React-based web interface
- Authenticated API ingestion
- Session history and comparison tools

### Development and Deployment

- Git and GitHub
- PyCharm
- Cloudflare deployment tooling
- Automated test suite

## Current Strategy

### Fibonacci 61.8% Paper Strategy

The active strategy looks for:

- A qualifying upward impulse
- A pullback toward the 61.8% Fibonacci retracement level
- Reduced pullback volume
- Bullish confirmation
- Defined entry, target, and trading stop-loss levels
- Acceptable reward-to-risk characteristics

Historical and forward-paper sessions use completed one-minute bars to avoid look-ahead bias.

## Supported Workflows

```bash
python main.py test
python main.py smoke YYYY-MM-DD
python main.py preflight YYYY-MM-DD
python main.py replay YYYY-MM-DD --speed 1000 --feed iex
python main.py fibonacci-paper --publish yes
python main.py dashboard-backfill START_DATE END_DATE --feed iex
python main.py backtest START_DATE END_DATE --feed iex
```

### Historical Dashboard Backfill

Historical Fibonacci sessions can be added to the Trading Desk without writing to Google Sheets or creating any broker activity:

```bash
ALPACA_DATA_FEED=iex python main.py dashboard-backfill \
  2026-07-01 2026-07-17 --feed iex
```

This workflow:

- Uses historical Fibonacci validation
- Publishes sessions with source `REPLAY`
- Calculates modeled outcomes
- Uses configured slippage assumptions
- Preserves incomplete sessions
- Never submits orders

## Data Quality

The scanner measures opening-bar completeness across prior sessions.

Symbols can be marked as:

- `SELECTED`
- `EXCLUDED_LOW_RELIABILITY`
- `NOT_SELECTED_RANKING_LIMIT`
- `FALLBACK_INSUFFICIENT_HISTORY`

A dashboard session is marked:

- `COMPLETE` when every selected symbol has all expected opening bars
- `INCOMPLETE` when one or more selected symbols are missing opening data

Incomplete sessions remain visible for auditability.

## Testing

The project currently has:

```text
158 passing tests
```

Run the full suite with:

```bash
python -m pytest -q
```

The tests cover strategy behavior, replay logic, dashboard payloads, outcome tracking, safety controls, scanner reliability, and workflow routing.

## Example Historical Paper Results

A July 2026 dashboard backfill produced a small initial sample that included both wins and losses.

These results are:

- Historical
- Hypothetical
- Modeled with slippage
- Not evidence of future performance
- Not generated from live submitted trades

The project intentionally presents unsuccessful trades alongside successful ones.

## Repository Structure

```text
.
├── main.py
├── trading_bot/
│   ├── bot.py
│   ├── dashboard_exporter.py
│   ├── fibonacci_dashboard.py
│   ├── fibonacci_paper.py
│   ├── historical_replay.py
│   ├── sheets_client.py
│   └── ...
├── tests/
├── reports/
├── logs/
└── README.md
```

## Configuration

Sensitive values are loaded through environment variables and are not committed to GitHub.

Typical configuration includes:

```text
ALPACA_API_KEY
ALPACA_SECRET_KEY
ALPACA_DATA_FEED
DASHBOARD_INGEST_KEY
DASHBOARD_SITE_TOKEN
DASHBOARD_URL
ACTIVE_STRATEGY
TRADING_RUN_MODE
```

Do not commit `.env`, service-account files, API keys, or private dashboard credentials.

## Disclaimer

This project is for software engineering, market-data research, and paper-trading analysis only.

It is not financial advice, does not guarantee profitability, and should not be used to make live trading decisions without independent review, risk controls, and regulatory consideration.
