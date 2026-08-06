from __future__ import annotations

import json
from pathlib import Path

from trading_bot.dashboard_exporter import DashboardExporter
from trading_bot.models import Stock


def main() -> None:
    stock = Stock(symbol="OPEN")
    stock.signal = "INVEST"
    stock.opening_bar = {
        "o": 4.40,
        "h": 4.50,
        "l": 4.10,
        "c": 4.30,
    }
    stock.atr = 0.25
    stock.strategy_name = "FIBONACCI_61_8"
    stock.strategy_status = (
        "ACTIVE PAPER/PREVIEW — NOT SUBMITTED"
    )
    stock.strategy_detail = (
        "Fibonacci preview fixture."
    )
    stock.limit_buy = 4.25
    stock.limit_sell = 4.60
    stock.stop_loss = 4.10
    stock.trading_stop_loss = 4.10
    stock.reward_risk = 2.33
    stock.confirmation_time = "10:08"
    stock.retracement_price = 4.18
    stock.impulse_atr_multiple = 0.72
    stock.pullback_volume_ratio = 0.64
    stock.webull_preview = {
        "status": "PREVIEW READY",
        "submitted": False,
        "quantity": 10,
        "limitBuy": 4.25,
        "target": 4.60,
        "tradingStopLoss": 4.10,
        "riskPerShare": 0.15,
        "plannedRisk": 1.50,
        "estimatedPositionValue": 42.50,
        "maxPositionValue": 77.72,
        "sizingConstraint": "POSITION_VALUE",
        "currency": "USD",
    }

    approvals = [
        {
            "symbol": "OPEN",
            "quantity": 10,
            "limitPrice": 4.25,
            "proposedExposure": 42.50,
            "status": "PENDING",
            "createdAt": "2026-08-06T18:30:00Z",
            "expiresAt": "2026-08-06T18:35:00Z",
        }
    ]

    payload = DashboardExporter.build_payload(
        date_str="2026-08-06",
        source="LIVE_FIBONACCI",
        stocks={"OPEN": stock},
        processed_bars={"OPEN": 38},
        data_feed="iex",
        run_mode="MANUAL",
        webull_approvals=approvals,
    )

    output = Path(
        "/tmp/webull-dashboard-fixture.json"
    )
    output.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    print(output)


if __name__ == "__main__":
    main()
