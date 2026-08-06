import pytest

from trading_bot.webull_account_parser import (
    WebullResponseError,
    parse_account_balance,
    parse_account_list,
    parse_open_orders,
    parse_positions,
)


def test_parses_single_cash_account():
    result = parse_account_list([
        {
            "account_id": "account-1",
            "account_type": "CASH",
        }
    ])

    assert result.account_id == "account-1"
    assert result.account_type == "CASH"


def test_rejects_margin_account_only_at_safety_layer():
    result = parse_account_list([
        {
            "account_id": "account-1",
            "account_type": "MARGIN",
        }
    ])

    assert result.account_type == "MARGIN"


def test_rejects_multiple_accounts():
    with pytest.raises(
        WebullResponseError,
        match="Exactly one",
    ):
        parse_account_list([
            {
                "account_id": "one",
                "account_type": "CASH",
            },
            {
                "account_id": "two",
                "account_type": "CASH",
            },
        ])


def test_rejects_unknown_account_type():
    with pytest.raises(
        WebullResponseError,
        match="not CASH or MARGIN",
    ):
        parse_account_list([
            {
                "account_id": "account-1",
                "account_type": "UNKNOWN",
            }
        ])


def test_parses_available_cash():
    result = parse_account_balance({
        "available_cash": "1000.25",
    })

    assert result.available_cash == 1000.25


def test_balance_fails_when_cash_missing():
    with pytest.raises(
        WebullResponseError,
        match="Available cash field was missing",
    ):
        parse_account_balance({
            "buying_power": "4000",
        })


def test_parses_position_market_value():
    result = parse_positions([
        {
            "symbol": "AAPL",
            "quantity": "2",
            "market_price": "100",
            "market_value": "200",
        }
    ])

    assert len(result) == 1
    assert result[0].market_value == 200.0


def test_rejects_inconsistent_position_value():
    with pytest.raises(
        WebullResponseError,
        match="did not match",
    ):
        parse_positions([
            {
                "symbol": "AAPL",
                "quantity": "2",
                "market_price": "100",
                "market_value": "250",
            }
        ])


def test_open_buy_order_reserves_remaining_exposure():
    result = parse_open_orders([
        {
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": "10",
            "filled_quantity": "4",
            "remain_quantity": "6",
            "limit_price": "20",
        }
    ])

    assert len(result) == 1
    assert result[0].remaining_quantity == 6.0
    assert result[0].reserved_exposure == 120.0


def test_open_sell_order_reserves_no_buy_exposure():
    result = parse_open_orders([
        {
            "symbol": "AAPL",
            "side": "SELL",
            "quantity": "5",
            "filled_quantity": "0",
            "limit_price": "20",
        }
    ])

    assert result[0].reserved_exposure == 0.0


def test_rejects_disagreeing_remaining_quantity():
    with pytest.raises(
        WebullResponseError,
        match="remaining quantity fields disagreed",
    ):
        parse_open_orders([
            {
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": "10",
                "filled_quantity": "4",
                "remain_quantity": "5",
                "limit_price": "20",
            }
        ])


def test_rejects_negative_numbers():
    with pytest.raises(
        WebullResponseError,
        match="cannot be negative",
    ):
        parse_account_balance({
            "available_cash": "-1",
        })
