from __future__ import annotations

import csv

from dataclasses import asdict, dataclass
from pathlib import Path

from .fibonacci_retracement import RetracementSetup


PAPER_RULE_NAME = (
    "FIB_61_8_MIN_0_50_ATR_DURATION_15_"
    "LOWER_PULLBACK_VOLUME"
)

PAPER_WARNING = "PAPER ONLY — NOT SUBMITTED"


@dataclass(frozen=True)
class FibonacciPaperRecord:
    date: str
    symbol: str
    data_feed: str
    paper_status: str
    submitted: str
    rule_name: str

    fibonacci_level: str
    retracement_ratio: float

    atr: float | None
    atr_pct: float | None

    impulse_start_time: str
    impulse_end_time: str
    impulse_atr_multiple: float | None
    impulse_duration_minutes: int | None
    impulse_average_volume: float | None

    retracement_touch_time: str
    retracement_price: float | None
    pullback_duration_minutes: int | None
    pullback_average_volume: float | None
    pullback_volume_ratio: float | None

    confirmation_time: str
    confirmation_above_vwap: bool | None

    entry_price: float | None
    entry_time: str
    stop_price: float | None
    target_price: float | None
    reward_risk: float | None

    outcome: str
    exit_time: str
    exit_price: float | None
    exit_reason: str
    net_return_pct: float | None

    modeled_slippage_bps: float
    detail: str


def qualifies_for_fibonacci_paper(
    setup: RetracementSetup,
) -> bool:
    return (
        setup.fibonacci_level == "FIB_61_8"
        and setup.setup_found
        and setup.impulse_atr_multiple is not None
        and setup.impulse_atr_multiple >= 0.50
        and setup.impulse_duration_minutes is not None
        and setup.impulse_duration_minutes >= 15
        and setup.pullback_volume_ratio is not None
        and setup.pullback_volume_ratio < 1.0
        and setup.reward_risk is not None
        and setup.reward_risk >= 1.5
    )


def build_fibonacci_paper_record(
    setup: RetracementSetup,
    *,
    modeled_slippage_bps: float,
) -> FibonacciPaperRecord | None:
    if not qualifies_for_fibonacci_paper(setup):
        return None

    return FibonacciPaperRecord(
        date=setup.date,
        symbol=setup.symbol,
        data_feed=setup.data_feed,
        paper_status=PAPER_WARNING,
        submitted="NO",
        rule_name=PAPER_RULE_NAME,
        fibonacci_level=setup.fibonacci_level,
        retracement_ratio=setup.retracement_ratio,
        atr=setup.atr,
        atr_pct=setup.atr_pct,
        impulse_start_time=setup.impulse_start_time,
        impulse_end_time=setup.impulse_end_time,
        impulse_atr_multiple=(
            setup.impulse_atr_multiple
        ),
        impulse_duration_minutes=(
            setup.impulse_duration_minutes
        ),
        impulse_average_volume=(
            setup.impulse_average_volume
        ),
        retracement_touch_time=(
            setup.retracement_touch_time
        ),
        retracement_price=setup.retracement_price,
        pullback_duration_minutes=(
            setup.pullback_duration_minutes
        ),
        pullback_average_volume=(
            setup.pullback_average_volume
        ),
        pullback_volume_ratio=(
            setup.pullback_volume_ratio
        ),
        confirmation_time=setup.confirmation_time,
        confirmation_above_vwap=(
            setup.confirmation_above_vwap
        ),
        entry_price=setup.entry_price,
        entry_time=setup.entry_time,
        stop_price=setup.stop_price,
        target_price=setup.target_price,
        reward_risk=setup.reward_risk,
        outcome=setup.outcome,
        exit_time=setup.exit_time,
        exit_price=setup.exit_price,
        exit_reason=setup.exit_reason,
        net_return_pct=setup.net_return_pct,
        modeled_slippage_bps=modeled_slippage_bps,
        detail=setup.detail,
    )


class FibonacciPaperLedger:
    """
    CSV-only paper ledger.

    Existing matching records are updated instead of duplicated,
    allowing a setup to progress from NO ENTRY to WIN or LOSS.
    """

    def __init__(
        self,
        path: str | Path = (
            "reports/fibonacci-paper/"
            "fibonacci_paper_ledger.csv"
        ),
    ) -> None:
        self.path = Path(path)

    @staticmethod
    def _record_key(
        row: dict[str, object],
    ) -> tuple[str, ...]:
        return (
            str(row.get("date", "")),
            str(row.get("symbol", "")),
            str(row.get("fibonacci_level", "")),
            str(row.get("impulse_start_time", "")),
            str(row.get("impulse_end_time", "")),
            str(row.get("confirmation_time", "")),
        )

    def upsert(
        self,
        records: list[FibonacciPaperRecord],
    ) -> Path:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        rows_by_key: dict[
            tuple[str, ...],
            dict[str, object],
        ] = {}

        if self.path.exists():
            with self.path.open(
                newline="",
                encoding="utf-8",
            ) as file:
                for row in csv.DictReader(file):
                    rows_by_key[
                        self._record_key(row)
                    ] = dict(row)

        for record in records:
            row = asdict(record)
            rows_by_key[
                self._record_key(row)
            ] = row

        fields = list(
            FibonacciPaperRecord
            .__dataclass_fields__
            .keys()
        )

        ordered_rows = sorted(
            rows_by_key.values(),
            key=lambda row: (
                str(row.get("date", "")),
                str(row.get("symbol", "")),
                str(
                    row.get(
                        "confirmation_time",
                        "",
                    )
                ),
            ),
            reverse=True,
        )

        with self.path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fields,
            )
            writer.writeheader()
            writer.writerows(ordered_rows)

        return self.path
