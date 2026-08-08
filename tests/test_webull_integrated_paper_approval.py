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


def test_integrated_confirmation_explains_cash_risk_block(
    capsys,
):
    bot = object.__new__(TradingBot)

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

    bot.request_webull_approval = (
        lambda symbol: ticket
    )
    bot.confirm_webull_approval = (
        lambda **kwargs: "APPROVED"
    )

    def blocked(**kwargs):
        raise RuntimeError(
            "PAPER_INSUFFICIENT_AVAILABLE_CASH"
        )

    bot.submit_webull_paper_order = blocked

    records = bot.process_webull_paper_confirmations(
        preview_results=[ready_preview()],
        input_fn=lambda prompt: "y",
    )

    output = capsys.readouterr().out

    assert records == []
    assert (
        "OPEN: BLOCKED BY PAPER RISK · insufficient "
        "simulated cash available for this order"
        in output
    )
    assert (
        "NO WEBULL BROKER ORDER WAS SUBMITTED"
        in output
    )


def test_integrated_confirmation_explains_daily_loss_halt(
    capsys,
):
    bot = object.__new__(TradingBot)

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

    bot.request_webull_approval = (
        lambda symbol: ticket
    )
    bot.confirm_webull_approval = (
        lambda **kwargs: "APPROVED"
    )

    def blocked(**kwargs):
        raise RuntimeError(
            "PAPER_DAILY_LOSS_LIMIT_REACHED"
        )

    bot.submit_webull_paper_order = blocked

    records = bot.process_webull_paper_confirmations(
        preview_results=[ready_preview()],
        input_fn=lambda prompt: "y",
    )

    output = capsys.readouterr().out

    assert records == []
    assert (
        "OPEN: BLOCKED BY PAPER RISK · daily "
        "realized-loss limit has been reached"
        in output
    )
    assert (
        "NO WEBULL BROKER ORDER WAS SUBMITTED"
        in output
    )


def test_paper_trade_failure_message_fails_closed():
    message = TradingBot._paper_trade_failure_message(
        RuntimeError(
            "PAPER_RISK_CHECK_FAILED:"
            "INVALID_PAPER_MAX_DAILY_LOSS"
        )
    )

    assert message == (
        "BLOCKED BY PAPER RISK · local paper risk "
        "status could not be verified safely"
    )


def test_paper_trade_failure_message_preserves_other_errors():
    message = TradingBot._paper_trade_failure_message(
        RuntimeError("PREVIEW_NOT_FOUND")
    )

    assert message == (
        "LOCAL PAPER trade failed · PREVIEW_NOT_FOUND"
    )
