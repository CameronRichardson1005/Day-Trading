from dataclasses import dataclass, field
from typing import Any


@dataclass
class Stock:
    symbol: str

    # Real-time 1-minute tracking
    running_high: float | None = None
    running_low: float | None = None

    minute_bars: list[dict[str, Any]] = field(
        default_factory=list
    )

    green_minutes: int = 0
    red_minutes: int = 0

    new_highs: int = 0
    new_lows: int = 0

    # Opening-bar and indicator data
    atr: float | None = None
    opening_bar: dict[str, Any] | None = None

    candle_range: float | None = None
    atr_threshold: float | None = None

    is_manipulation: bool = False
    is_red: bool = False

    proximity: str = ""

    # Strategy results
    signal: str = "NO INVEST"

    limit_buy: float | None = None
    limit_sell: float | None = None

    stop_loss: float | None = None
    trading_stop_loss: float | None = None