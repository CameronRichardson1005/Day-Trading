from datetime import UTC, datetime
from types import SimpleNamespace

from trading_bot.bot import TradingBot
from trading_bot.webull_approval import (
    WebullApprovalTicket,
)


def ready_preview():
    return {
        "symbol": "OPEN",
        "status": "PREVIEW READY",
        "quantity": 25,
        "limitBuy": 4.25,
        "estimatedPositionValue": 106.25,
        "tradingStopLoss": 4.05,
    }


def test_integrated_paper_confirmation_decline():
    bot = object.__new__(TradingBot)

    calls = []

    bot.request_webull_approval = (
        lambda symbol: calls.append(
            ("request", symbol)
        )
    )

    records = (
        bot.process_webull_paper_confirmations(
            preview_results=[ready_preview()],
            input_fn=lambda prompt: "n",
        )
    )

    assert records == []
    assert calls == []


def test_integrated_paper_confirmation_approves_and_records():
    bot = object.__new__(TradingBot)

    calls = []

    ticket = WebullApprovalTicket(
        approval_id="approval-1",
        approval_token="secret-token",
        symbol="OPEN",
        quantity=25,
        limit_price=4.25,
        proposed_exposure=106.25,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
    )

    def request(symbol):
        calls.append(
            ("request", symbol)
        )
        return ticket

    def confirm(**kwargs):
        calls.append(
            (
                "confirm",
                kwargs["approval_id"],
                kwargs["approval_token"],
            )
        )
        return "APPROVED"

    def submit(**kwargs):
        calls.append(
            (
                "submit",
                kwargs["symbol"],
                kwargs["approval_id"],
                kwargs["approval_token"],
            )
        )
        return SimpleNamespace(
            status="PAPER SUBMITTED",
        )

    bot.request_webull_approval = request
    bot.confirm_webull_approval = confirm
    bot.submit_webull_paper_order = submit

    records = (
        bot.process_webull_paper_confirmations(
            preview_results=[ready_preview()],
            input_fn=lambda prompt: "y",
        )
    )

    assert len(records) == 1

    assert calls == [
        ("request", "OPEN"),
        (
            "confirm",
            "approval-1",
            "secret-token",
        ),
        (
            "submit",
            "OPEN",
            "approval-1",
            "secret-token",
        ),
    ]


def test_integrated_paper_confirmation_skips_failed_preview():
    bot = object.__new__(TradingBot)

    records = (
        bot.process_webull_paper_confirmations(
            preview_results=[{
                "symbol": "OPEN",
                "status": "PREVIEW FAILED",
            }],
            input_fn=lambda prompt: (
                (_ for _ in ()).throw(
                    AssertionError(
                        "Should not prompt."
                    )
                )
            ),
        )
    )

    assert records == []
