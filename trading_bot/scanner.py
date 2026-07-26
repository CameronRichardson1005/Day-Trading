from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class StockStats:
    symbol: str
    valid_bars: int
    avg_volume: float
    avg_price: float
    avg_range: float
    avg_range_pct: float

    @property
    def ranking_score(self) -> float:
        return (
            self.avg_range_pct
            * (self.avg_volume / 1_000_000)
        )


@dataclass(frozen=True)
class ScannerRules:
    minimum_valid_bars: int = 20
    minimum_price: float = 2.0
    maximum_price: float = 30.0
    minimum_average_volume: float = 500_000
    minimum_average_range: float = 0.20
    minimum_average_range_pct: float = 4.0
    candidate_limit: int = 3


class StockScanner:
    def __init__(
            self,
            current_symbols: Sequence[str],
            rules: ScannerRules | None = None,
    ) -> None:
        self.current_symbols = list(
            dict.fromkeys(current_symbols)
        )
        self.rules = rules or ScannerRules()

    def is_eligible(self, stats: StockStats) -> bool:
        rules = self.rules

        return (
            stats.valid_bars
            >= rules.minimum_valid_bars
            and rules.minimum_price
            <= stats.avg_price
            <= rules.maximum_price
            and stats.avg_volume
            >= rules.minimum_average_volume
            and stats.avg_range
            >= rules.minimum_average_range
            and stats.avg_range_pct
            >= rules.minimum_average_range_pct
        )

    def select_candidates(
            self,
            statistics: Iterable[StockStats],
    ) -> list[StockStats]:
        current_set = set(self.current_symbols)

        eligible = [
            stats
            for stats in statistics
            if stats.symbol not in current_set
            and self.is_eligible(stats)
        ]

        eligible.sort(
            key=lambda stats: (
                -stats.ranking_score,
                stats.symbol,
            )
        )

        return eligible[
            :self.rules.candidate_limit
        ]

    def select_symbols(
            self,
            statistics: Iterable[StockStats],
    ) -> list[str]:
        selected_candidates = self.select_candidates(
            statistics
        )

        return self.current_symbols + [
            stats.symbol
            for stats in selected_candidates
        ]
