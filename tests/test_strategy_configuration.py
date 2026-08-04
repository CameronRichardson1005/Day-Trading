import importlib

import pytest

import trading_bot.config as config


def test_supported_strategies_preserve_manipulation_and_fibonacci():
    assert "MANIPULATION_OPENING_15M" in (
        config.SUPPORTED_STRATEGIES
    )
    assert "FIBONACCI_61_8" in config.SUPPORTED_STRATEGIES


def test_active_strategy_is_supported():
    assert config.ACTIVE_STRATEGY in config.SUPPORTED_STRATEGIES


def test_real_order_submission_is_disabled():
    assert config.REAL_ORDER_SUBMISSION_ENABLED is False


def test_invalid_active_strategy_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "ACTIVE_STRATEGY",
        "UNSUPPORTED_STRATEGY",
    )

    with pytest.raises(
        RuntimeError,
        match="ACTIVE_STRATEGY must be one of",
    ):
        importlib.reload(config)

    monkeypatch.setenv(
        "ACTIVE_STRATEGY",
        "MANIPULATION_OPENING_15M",
    )
    importlib.reload(config)
