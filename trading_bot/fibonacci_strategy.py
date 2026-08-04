from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .fibonacci_paper import qualifies_for_fibonacci_paper
from .fibonacci_retracement import analyse_symbol_day
from .models import Stock


class Fibonacci618Strategy:
    """
    Active paper/preview adapter for the preserved Fibonacci
    61.8% retracement rules.

    This adapter maps a qualifying Fibonacci setup onto the
    existing Stock fields used by Google Sheets, the Cloudflare
    dashboard, and Webull preview generation.

    It never submits an order.
    """

    name = "FIBONACCI_61_8"
    status = "ACTIVE PAPER/PREVIEW — NOT SUBMITTED"

    def evaluate(
        self,
        *,
        stock: Stock,
        date_str: str,
        bars: Sequence[dict[str, Any]],
        atr: float | None,
        data_feed: str,
        slippage_bps: float = 15.0,
    ) -> Stock:
        self._reset_active_fields(stock)

        stock.strategy_name = self.name
        stock.strategy_status = self.status
        stock.atr = atr

        setups = analyse_symbol_day(
            date_str=date_str,
            symbol=stock.symbol,
            data_feed=data_feed,
            bars=list(bars),
            atr=atr,
            minimum_impulse_atr=0.50,
            slippage_bps=slippage_bps,
            commission_per_share=0.0,
        )

        setup = next(
            (
                candidate
                for candidate in setups
                if candidate.fibonacci_level == "FIB_61_8"
            ),
            None,
        )

        stock.strategy_detail = (
            setup.detail
            if setup is not None
            else "FIB_61_8 setup was not evaluated."
        )

        if setup is None or not qualifies_for_fibonacci_paper(setup):
            stock.signal = "NO INVEST"

            if setup is not None:
                stock.strategy_rejection_reason = (
                    setup.rejection_reason
                    or setup.detail
                    or "FIBONACCI_RULES_NOT_SATISFIED"
                )

            return stock

        if (
            setup.entry_price is None
            or setup.stop_price is None
            or setup.target_price is None
        ):
            stock.signal = "NO INVEST"
            stock.strategy_rejection_reason = (
                "QUALIFYING_SETUP_MISSING_LEVELS"
            )
            return stock

        stock.signal = "INVEST"
        stock.limit_buy = float(setup.entry_price)
        stock.limit_sell = float(setup.target_price)

        # The Fibonacci structural stop becomes both the displayed
        # and trading stop. No manipulation STOP_BUFFER is applied.
        stock.stop_loss = float(setup.stop_price)
        stock.trading_stop_loss = float(setup.stop_price)

        stock.reward_risk = setup.reward_risk
        stock.confirmation_time = setup.confirmation_time
        stock.retracement_price = setup.retracement_price
        stock.impulse_atr_multiple = setup.impulse_atr_multiple
        stock.pullback_volume_ratio = setup.pullback_volume_ratio
        stock.strategy_rejection_reason = ""

        return stock

    @staticmethod
    def _reset_active_fields(stock: Stock) -> None:
        stock.signal = "NO INVEST"
        stock.limit_buy = None
        stock.limit_sell = None
        stock.stop_loss = None
        stock.trading_stop_loss = None
        stock.webull_preview = None

        stock.strategy_detail = ""
        stock.strategy_rejection_reason = ""
        stock.reward_risk = None
        stock.confirmation_time = ""
        stock.retracement_price = None
        stock.impulse_atr_multiple = None
        stock.pullback_volume_ratio = None
