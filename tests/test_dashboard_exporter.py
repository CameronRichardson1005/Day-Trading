from trading_bot.dashboard_exporter import (
    DashboardExporter,
)
from trading_bot.models import Stock


def complete_stock(
        symbol="TEST",
        signal="INVEST",
):
    stock = Stock(symbol=symbol)
    stock.opening_bar = {
        "o": 10.0,
        "h": 11.0,
        "l": 9.0,
        "c": 9.5,
    }
    stock.atr = 1.0
    stock.candle_range = 2.0
    stock.atr_threshold = 0.5
    stock.is_manipulation = True
    stock.is_red = True
    stock.signal = signal
    stock.limit_buy = 9.0
    stock.limit_sell = 9.382
    stock.stop_loss = 8.809
    stock.trading_stop_loss = 8.759
    return stock


def test_complete_invest_includes_levels():
    payload = DashboardExporter.build_payload(
        date_str="2026-07-23",
        source="REPLAY",
        stocks={
            "TEST": complete_stock(),
        },
        processed_bars={
            "TEST": 15,
        },
    )

    assert payload["status"] == "COMPLETE"
    assert payload["dataFeed"] == "SIP"
    assert payload["symbols"][0]["signal"] == "INVEST"
    assert payload["symbols"][0]["levels"] == {
        "buy": 9.0,
        "target": 9.382,
        "stop": 8.809,
        "tradingStop": 8.759,
    }


def test_incomplete_symbol_suppresses_signal_and_levels():
    payload = DashboardExporter.build_payload(
        date_str="2026-07-23",
        source="LIVE",
        stocks={
            "TEST": complete_stock(),
        },
        processed_bars={
            "TEST": 14,
        },
    )

    symbol = payload["symbols"][0]
    assert payload["status"] == "INCOMPLETE"
    assert symbol["signal"] == "WARNING"
    assert "levels" not in symbol


def test_missing_strategy_result_is_incomplete():
    stock = Stock(symbol="TEST")

    payload = DashboardExporter.build_payload(
        date_str="2026-07-23",
        source="LIVE",
        stocks={
            "TEST": stock,
        },
        processed_bars={
            "TEST": 15,
        },
    )

    symbol = payload["symbols"][0]
    assert payload["status"] == "INCOMPLETE"
    assert symbol["detail"] == "strategy unavailable"
    assert symbol["signal"] == "WARNING"


def test_no_invest_never_includes_levels():
    payload = DashboardExporter.build_payload(
        date_str="2026-07-23",
        source="REPLAY",
        stocks={
            "TEST": complete_stock(
                signal="NO INVEST"
            ),
        },
        processed_bars={
            "TEST": 15,
        },
    )

    symbol = payload["symbols"][0]
    assert payload["status"] == "COMPLETE"
    assert symbol["signal"] == "NO INVEST"
    assert "levels" not in symbol


def test_publish_skips_when_key_is_missing():
    exporter = DashboardExporter(
        ingest_key="",
        post_fn=lambda *args, **kwargs: (
            None
        ),
    )

    assert exporter.publish(
        date_str="2026-07-23",
        source="REPLAY",
        stocks={
            "TEST": complete_stock(),
        },
        processed_bars={
            "TEST": 15,
        },
    ) is None


def test_publish_uses_read_only_endpoint_contract():
    calls = []

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "accepted": True,
                "id": "replay-2026-07-23",
                "status": "COMPLETE",
            }

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    exporter = DashboardExporter(
        url="https://example.test/api/sessions/latest",
        ingest_key="secret",
        site_token="site-token",
        post_fn=post,
    )

    result = exporter.publish(
        date_str="2026-07-23",
        source="REPLAY",
        stocks={
            "TEST": complete_stock(),
        },
        processed_bars={
            "TEST": 15,
        },
    )

    assert result["accepted"] is True
    assert calls[0][0].endswith(
        "/api/sessions/latest"
    )
    assert calls[0][1]["headers"] == {
        "x-dashboard-key": "secret",
        "OAI-Sites-Authorization": (
            "Bearer site-token"
        ),
    }
    assert calls[0][1]["timeout"] == (5, 15)
    assert calls[0][1]["json"]["dataFeed"] == "SIP"


def test_complete_invest_includes_outcome():
    stock = complete_stock()
    stock.outcome = {
        "status": "WIN",
        "entryTime": "09:45",
        "exitTime": "10:12",
        "entryPrice": 9.0,
        "exitPrice": 9.382,
        "pnlPerShare": 0.382,
        "returnPct": 4.244444,
        "detail": "Profit target reached first.",
    }

    payload = DashboardExporter.build_payload(
        date_str="2026-07-23",
        source="REPLAY",
        stocks={
            "TEST": stock,
        },
        processed_bars={
            "TEST": 15,
        },
    )

    assert payload["symbols"][0]["outcome"] == (
        stock.outcome
    )
