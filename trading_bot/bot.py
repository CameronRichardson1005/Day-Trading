import os
import time as time_module

from contextlib import redirect_stdout
from datetime import datetime, time, timedelta
from io import StringIO
from pathlib import Path
from threading import Thread
from zoneinfo import ZoneInfo

from .webull_preview_service import WebullPreviewService
from .alpaca_client import AlpacaClient
from .backtest import (
    BacktestReport,
    ReplaySession,
    market_regimes_by_date,
    weekday_dates,
)
from .config import (
    CANDIDATE_TICKERS,
    MARKET_DATA_FEED,
    TICKERS,
)
from .dashboard_exporter import DashboardExporter
from .models import Stock
from .replay import HistoricalReplay
from .scanner import StockScanner
from .sheets_client import SheetsClient
from .stream_client import AlpacaStockStream
from .strategy import ManipulationStrategy
from .tracker import MinuteTracker


class TradingBot:
    def __init__(self) -> None:
        self.stocks = {
            symbol: Stock(symbol=symbol)
            for symbol in TICKERS
        }

        self.symbols_csv = ",".join(self.stocks.keys())

        self.alpaca = AlpacaClient()
        self.strategy = ManipulationStrategy()
        self.scanner = StockScanner(
            current_symbols=TICKERS,
        )
        self.scanner_statistics = None
        self.symbol_reliability = None

        self.sheets = None
        self.tracker = None
        self.dashboard = DashboardExporter()

    def refresh_symbols_for_date(
            self,
            date_str: str,
            data_feed: str = MARKET_DATA_FEED,
    ) -> list[str]:
        self.scanner_statistics = None
        self.symbol_reliability = None

        fallback_symbols = list(
            self.scanner.current_symbols
        )

        try:
            statistics = (
                self.alpaca.get_scanner_statistics(
                    symbols_csv=",".join(
                        CANDIDATE_TICKERS
                    ),
                    date_str=date_str,
                    feed=data_feed,
                )
            )

            reliability = None

            try:
                reliability = (
                    self.alpaca.get_opening_reliability(
                        symbols_csv=",".join(
                            dict.fromkeys(
                                TICKERS
                                + CANDIDATE_TICKERS
                            )
                        ),
                        date_str=date_str,
                        feed=data_feed,
                    )
                )
            except Exception as reliability_error:
                print(
                    "Opening reliability check failed. "
                    "Continuing without reliability filtering. "
                    f"Reason: {reliability_error}"
                )

            selected_symbols = (
                self.scanner.select_symbols(
                    statistics,
                    reliability=reliability,
                )
            )

            if reliability is not None:
                for record in reliability:
                    print(
                        f"{record.symbol}: "
                        f"{data_feed.upper()} opening reliability "
                        f"{record.completeness:.1%} across "
                        f"{record.usable_days} day(s)."
                    )

            if reliability is not None:
                selected_set = set(selected_symbols)

                for record in reliability:
                    if (
                        record.usable_days
                        < self.scanner.rules.minimum_reliability_days
                    ):
                        status = (
                            "FALLBACK - INSUFFICIENT HISTORY"
                        )
                    elif record.symbol in selected_set:
                        status = "SELECTED"
                    elif (
                        record.completeness
                        < self.scanner.rules.minimum_opening_completeness
                    ):
                        status = (
                            "EXCLUDED - LOW IEX RELIABILITY"
                        )
                    else:
                        status = (
                            "NOT SELECTED - RANKING LIMIT"
                        )

                    print(
                        f"{record.symbol}: {status}"
                    )

            if reliability is not None:
                selected_set = set(selected_symbols)
                reliability_payload = []

                for record in reliability:
                    if (
                        record.usable_days
                        < self.scanner.rules.minimum_reliability_days
                    ):
                        status = (
                            "FALLBACK_INSUFFICIENT_HISTORY"
                        )
                    elif record.symbol in selected_set:
                        status = "SELECTED"
                    elif (
                        record.completeness
                        < self.scanner.rules.minimum_opening_completeness
                    ):
                        status = (
                            "EXCLUDED_LOW_RELIABILITY"
                        )
                    else:
                        status = (
                            "NOT_SELECTED_RANKING_LIMIT"
                        )

                    reliability_payload.append(
                        {
                            "symbol": record.symbol,
                            "completeness": round(
                                record.completeness,
                                6,
                            ),
                            "usableDays": (
                                record.usable_days
                            ),
                            "totalBars": (
                                record.total_bars
                            ),
                            "expectedBars": (
                                record.expected_bars
                            ),
                            "status": status,
                        }
                    )

                self.symbol_reliability = (
                    reliability_payload
                )

            self.scanner_statistics = statistics

        except Exception as error:
            print(
                "Stock scanner failed. "
                "Using existing tickers."
            )
            print(f"Scanner error: {error}")

            selected_symbols = fallback_symbols

        existing_stocks = self.stocks

        self.stocks = {
            symbol: existing_stocks.get(
                symbol,
                Stock(symbol=symbol),
            )
            for symbol in selected_symbols
        }

        self.symbols_csv = ",".join(selected_symbols)

        # Rebuild the tracker when Sheets are next
        # initialised so it receives the new symbols.
        self.tracker = None

        print(
            "Selected symbols:",
            ", ".join(selected_symbols),
        )

        return selected_symbols

    def initialise_sheets(
            self,
            write_sheets: bool = True,
    ) -> None:
        if write_sheets and self.sheets is None:
            self.sheets = SheetsClient()

        if self.tracker is None:
            self.tracker = MinuteTracker(
                alpaca=self.alpaca,
                sheets=self.sheets,
                stocks=self.stocks,
                symbols_csv=self.symbols_csv,
                write_sheets=write_sheets,
            )

    def run(self) -> None:
        print("===================================")
        print(" Professional Day Trading Bot")
        print("===================================")
        print()

        print("Tracking")

        for stock in self.stocks.values():
            print(stock.symbol)

        print()
        print("Testing Alpaca market-data connection...")

        try:
            recent_bars = self.alpaca.test_connection(
                self.symbols_csv
            )

            successful_symbols = [
                symbol
                for symbol, bar in recent_bars.items()
                if bar is not None
            ]

            missing_symbols = [
                symbol
                for symbol, bar in recent_bars.items()
                if bar is None
            ]

            print("Alpaca connection successful.")
            print(
                "Symbols returned:",
                ", ".join(successful_symbols),
            )

            if missing_symbols:
                print(
                    "No recent bars returned for:",
                    ", ".join(missing_symbols),
                )

        except Exception as error:
            print("Alpaca connection test failed.")
            print(f"Error: {error}")
            return

        print()
        print("Testing Google Sheets connection...")

        try:
            self.initialise_sheets()

            worksheet_names = self.sheets.test_connection()

            print("Google Sheets connection successful.")
            print(
                "Worksheets:",
                ", ".join(worksheet_names),
            )

        except Exception as error:
            print("Google Sheets connection test failed.")
            print(f"Error: {error}")
            return

        print()
        print("Bot Started Successfully")

    def run_scanner_smoke(
            self,
            date_str: str | None = None,
    ) -> bool:
        if date_str is None:
            eastern = ZoneInfo(
                "America/New_York"
            )
            date_str = (
                datetime.now(eastern)
                .date()
                .isoformat()
            )

        print()
        print("===================================")
        print(" Scanner Dashboard Smoke Test")
        print("===================================")
        print(f"Scanner date: {date_str}")

        selected_symbols = (
            self.refresh_symbols_for_date(date_str)
        )

        if self.scanner_statistics is None:
            print(
                "Smoke test failed because scanner "
                "statistics were unavailable."
            )
            return False

        if self.sheets is None:
            self.sheets = SheetsClient()

        self.sheets.write_scanner_dashboard(
            date_str=date_str,
            statistics=self.scanner_statistics,
            selected_symbols=selected_symbols,
            scanner=self.scanner,
        )

        print()
        print(
            "Scanner dashboard smoke test "
            "completed successfully."
        )
        print(
            "No minute tracking, strategy, or "
            "order workflow was started."
        )

        return True

    def run_preflight(
            self,
            date_str: str | None = None,
    ) -> bool:
        if date_str is None:
            eastern = ZoneInfo(
                "America/New_York"
            )
            date_str = (
                datetime.now(eastern)
                .date()
                .isoformat()
            )

        print()
        print("===================================")
        print(" Trading Bot Preflight")
        print("===================================")
        print(f"Preflight date: {date_str}")

        selected_symbols = (
            self.refresh_symbols_for_date(date_str)
        )

        if self.scanner_statistics is None:
            print(
                "Preflight failed: scanner statistics "
                "were unavailable."
            )
            return False

        if not selected_symbols:
            print(
                "Preflight failed: no symbols were "
                "selected."
            )
            return False

        print("Scanner check passed.")
        print(
            "Checking Google Sheets and tracker "
            "initialisation..."
        )

        try:
            self.initialise_sheets()
            worksheet_names = (
                self.sheets.test_connection()
            )
        except Exception as error:
            print(
                "Preflight failed during Google Sheets "
                "or tracker initialisation."
            )
            print(f"Preflight error: {error}")
            return False

        required_worksheets = {
            "Scanner Dashboard",
            "1 minute intervals",
        }

        missing_worksheets = sorted(
            required_worksheets.difference(
                worksheet_names
            )
        )

        if missing_worksheets:
            print(
                "Preflight failed: missing worksheets: "
                + ", ".join(missing_worksheets)
            )
            return False

        if self.tracker is None:
            print(
                "Preflight failed: minute tracker was "
                "not initialised."
            )
            return False

        print("Google Sheets check passed.")
        print("Minute tracker initialisation passed.")
        print()
        print("Preflight completed successfully.")
        print(
            "No minute tracking, strategy, dashboard "
            "write, or order workflow was started."
        )

        return True

    def run_live_tracker(
            self,
            write_sheets: bool = True,
            publish_dashboard: bool = True,
    ) -> None:
        eastern = ZoneInfo("America/New_York")
        utc = ZoneInfo("UTC")

        today_eastern = datetime.now(eastern).date()

        market_open_eastern = datetime.combine(
            today_eastern,
            time(hour=9, minute=30),
            tzinfo=eastern,
        )

        market_end_eastern = datetime.combine(
            today_eastern,
            time(hour=9, minute=44),
            tzinfo=eastern,
        )

        now_eastern = datetime.now(eastern)
        earliest_start = (
            market_open_eastern
            - timedelta(minutes=10)
        )
        latest_start = (
            market_end_eastern
            + timedelta(minutes=6)
        )

        if now_eastern < earliest_start:
            print(
                "Live workflow skipped: current New York "
                "time is earlier than 09:20."
            )
            return

        if now_eastern > latest_start:
            print(
                "Live workflow skipped: the 09:30–09:45 "
                "opening window has already passed."
            )
            return

        window_start = market_open_eastern.astimezone(
            utc
        ).replace(tzinfo=None)

        window_end = market_end_eastern.astimezone(
            utc
        ).replace(tzinfo=None)

        date_str = today_eastern.strftime("%Y-%m-%d")

        selected_symbols = (
            self.refresh_symbols_for_date(date_str)
        )
        self.initialise_sheets(
            write_sheets=write_sheets,
        )

        if not write_sheets:
            print(
                "DRY-RUN MODE: Google Sheets and "
                "scanner-dashboard writes are disabled."
            )
        elif self.scanner_statistics is not None:
            try:
                self.sheets.write_scanner_dashboard(
                    date_str=date_str,
                    statistics=self.scanner_statistics,
                    selected_symbols=selected_symbols,
                    scanner=self.scanner,
                )
            except Exception as error:
                print(
                    "Scanner dashboard update failed. "
                    "Live tracking will continue."
                )
                print(f"Dashboard error: {error}")
        else:
            print(
                "Scanner dashboard skipped because "
                "scanner statistics were unavailable."
            )

        print()
        print("Starting real-time 1-minute tracker...")
        print(
            "Tracking window:",
            market_open_eastern.strftime("%H:%M"),
            "to",
            "09:45",
            "New York time",
        )

        stream_result: dict[str, object] = {
            "bars": {},
            "error": None,
        }

        stream_stop_time = (
            window_end
            + timedelta(minutes=1)
            + timedelta(seconds=5)
        )

        def collect_stream() -> None:
            try:
                stream = AlpacaStockStream(
                    symbols=selected_symbols,
                    feed=MARKET_DATA_FEED,
                )
                stream_result["bars"] = (
                    stream.collect_until(
                        stop_time=stream_stop_time,
                    )
                )
            except Exception as error:
                stream_result["error"] = error

        stream_thread = Thread(
            target=collect_stream,
            name="alpaca-market-data-stream",
            daemon=True,
        )

        print(
            f"Starting {MARKET_DATA_FEED.upper()} "
            "WebSocket collector..."
        )
        stream_thread.start()

        self.tracker.track_window(
            date_str=date_str,
            window_start=window_start,
            window_end=window_end,
        )

        stream_thread.join(timeout=10)

        stream_error = stream_result.get("error")
        streamed_bars = stream_result.get("bars", {})

        if stream_thread.is_alive():
            print(
                "WebSocket collector did not stop in time. "
                "Continuing with reconciled REST bars."
            )
        elif stream_error is not None:
            print(
                "WebSocket collector failed. "
                "Reconciled REST tracking was preserved."
            )
            print(f"WebSocket error: {stream_error}")
        elif isinstance(streamed_bars, dict):
            streamed_count = sum(
                len(bars)
                for bars in streamed_bars.values()
                if isinstance(bars, list)
            )

            print(
                f"Merging {streamed_count} WebSocket bar(s)..."
            )

            self.tracker.merge_stream_bars(
                streamed_bars=streamed_bars,
            )

            print(
                "WebSocket bars merged successfully."
            )

        processed_bars = {
            symbol: (
                stock.green_minutes
                + stock.red_minutes
            )
            for symbol, stock in getattr(self, "stocks", {}).items()
        }

        print()
        print("Calculating live strategy results...")

        try:
            if write_sheets:
                self.run_strategy_and_write(
                    date_str=date_str,
                )
            else:
                self.calculate_strategy(
                    date_str=date_str,
                )

            print(
                "Live strategy calculation completed."
            )
        except Exception as error:
            print(
                "Live strategy calculation failed. "
                "Dashboard will preserve data warnings."
            )
            print(f"Strategy error: {error}")

        if publish_dashboard:
            self._publish_dashboard_session(
                date_str=date_str,
                source="LIVE",
                processed_bars=processed_bars,
            )
        else:
            print(
                "DRY-RUN MODE: Dashboard upload was skipped."
            )

    def _publish_dashboard_session(
            self,
            date_str: str,
            source: str,
            processed_bars: dict[str, int],
            data_feed: str = MARKET_DATA_FEED,
    ) -> None:
        try:
            result = self.dashboard.publish(
                date_str=date_str,
                source=source,
                stocks=self.stocks,
                processed_bars=processed_bars,
                data_feed=data_feed,
                symbol_reliability=(
                    self.symbol_reliability
                ),
                run_mode=os.getenv(
                    "TRADING_RUN_MODE",
                    (
                        "REPLAY"
                        if source == "REPLAY"
                        else "MANUAL"
                    ),
                ),
            )
        except Exception as error:
            print(
                "Dashboard upload failed. "
                "Trading-bot processing is unchanged."
            )
            print(f"Dashboard error: {error}")
            return

        if result is None:
            print(
                "Dashboard upload skipped: "
                "DASHBOARD_INGEST_KEY is not configured."
            )
            return

        print(
            "Dashboard session uploaded: "
            f"{result['status']}."
        )

    def run_replay(
            self,
            date_str: str,
            speed: float = 60.0,
        publish_dashboard: bool = True,
        data_feed: str = MARKET_DATA_FEED,
        slippage_bps: float = 0.0,
        commission_per_share: float = 0.0,
    ) -> ReplaySession:
        data_feed = data_feed.strip().lower()
        if data_feed not in {"iex", "sip"}:
            raise ValueError(
                "Market-data feed must be 'iex' or 'sip'."
            )
        try:
            trading_date = datetime.strptime(
                date_str,
                "%Y-%m-%d",
            ).date()
        except ValueError as error:
            raise ValueError(
                "Replay date must use YYYY-MM-DD format."
            ) from error

        if trading_date.weekday() >= 5:
            raise ValueError(
                "Replay date must be a weekday."
            )

        if speed < 0:
            raise ValueError(
                "Replay speed cannot be negative."
            )

        eastern = ZoneInfo("America/New_York")
        utc = ZoneInfo("UTC")

        window_start = datetime.combine(
            trading_date,
            time(hour=9, minute=30),
            tzinfo=eastern,
        ).astimezone(utc)

        window_end = (
            window_start
            + timedelta(minutes=15)
            - timedelta(seconds=1)
        )

        print()
        print("===================================")
        print(" Historical Trading Replay")
        print("===================================")
        print(f"Trading date: {date_str}")
        print(f"Replay speed: {speed:g}x")
        print(f"Market-data feed: {data_feed.upper()}")
        print(
            "READ-ONLY MODE: Google Sheets, Orders, "
            "and trading are disabled."
        )

        self.refresh_symbols_for_date(
            date_str,
            data_feed=data_feed,
        )

        bars_by_symbol = (
            self.alpaca.get_historical_1min_bars(
                symbols_csv=self.symbols_csv,
                start_iso=window_start.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                end_iso=window_end.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                feed=data_feed,
            )
        )

        atrs = self.alpaca.get_previous_day_ranges_all(
            symbols_csv=self.symbols_csv,
            date_str=date_str,
            feed=data_feed,
        )

        replay = HistoricalReplay(
            stocks=self.stocks,
            strategy=self.strategy,
            speed=speed,
        )

        summary = replay.run(
            date_str=date_str,
            window_start=window_start,
            bars_by_symbol=bars_by_symbol,
            atrs=atrs,
            data_feed=data_feed,
        )
        summary.atr_diagnostics = getattr(
            self.alpaca,
            "last_atr_diagnostics",
            {},
        )

        outcome_start = datetime.combine(
            trading_date,
            time(hour=9, minute=45),
            tzinfo=eastern,
        ).astimezone(utc)

        outcome_end = datetime.combine(
            trading_date,
            time(hour=16),
            tzinfo=eastern,
        ).astimezone(utc)

        outcome_bars = (
            self.alpaca.get_historical_1min_bars(
                symbols_csv=self.symbols_csv,
                start_iso=outcome_start.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                end_iso=outcome_end.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                feed=data_feed,
            )
        )

        replay.calculate_outcomes(
            bars_by_symbol=outcome_bars,
            slippage_bps=slippage_bps,
            commission_per_share=commission_per_share,
        )

        print()
        print("===== REPLAY RESULTS =====")

        for symbol, stock in self.stocks.items():
            processed = summary.processed_bars[symbol]

            print()
            print(f"Symbol: {symbol}")
            print(
                f"Bars processed: {processed}/15"
            )
            print(
                f"Green/Red minutes: "
                f"{stock.green_minutes}/"
                f"{stock.red_minutes}"
            )
            print(
                f"New highs/lows: "
                f"{stock.new_highs}/"
                f"{stock.new_lows}"
            )

            if stock.opening_bar is None:
                print("Opening candle: incomplete")
                print("Signal: NO INVEST")
                continue

            print(
                "Opening O/H/L/C: "
                f"{float(stock.opening_bar['o']):.4f} / "
                f"{float(stock.opening_bar['h']):.4f} / "
                f"{float(stock.opening_bar['l']):.4f} / "
                f"{float(stock.opening_bar['c']):.4f}"
            )

            if stock.atr is None:
                print("ATR: unavailable")
            else:
                print(f"ATR: {stock.atr:.4f}")

            print(f"Signal: {stock.signal}")

        print()
        print("Historical replay completed.")
        print(
            "No spreadsheets or orders were created."
        )

        session = ReplaySession(
            date=date_str,
            stocks={
                symbol: stock
                for symbol, stock in self.stocks.items()
            },
            summary=summary,
        )

        if publish_dashboard:
            self._publish_dashboard_session(
                date_str=date_str,
                source="REPLAY",
                processed_bars=summary.processed_bars,
                data_feed=data_feed,
            )

        return session

    def run_backtest(
            self,
            start_date: str,
            end_date: str,
        output_directory: str | Path = "reports",
        data_feed: str = MARKET_DATA_FEED,
        slippage_bps: float = 0.0,
        commission_per_share: float = 0.0,
        train_fraction: float = 0.70,
    ) -> BacktestReport:
        data_feed = data_feed.strip().lower()
        if data_feed not in {"iex", "sip"}:
            raise ValueError(
                "Market-data feed must be 'iex' or 'sip'."
            )
        if slippage_bps < 0:
            raise ValueError(
                "Slippage cannot be negative."
            )
        if commission_per_share < 0:
            raise ValueError(
                "Commission cannot be negative."
            )
        if not 0.1 <= train_fraction <= 0.9:
            raise ValueError(
                "Train fraction must be between 0.1 and 0.9."
            )
        try:
            start = datetime.strptime(
                start_date,
                "%Y-%m-%d",
            ).date()
            end = datetime.strptime(
                end_date,
                "%Y-%m-%d",
            ).date()
        except ValueError as error:
            raise ValueError(
                "Backtest dates must use YYYY-MM-DD format."
            ) from error

        dates = weekday_dates(start, end)
        if not dates:
            raise ValueError(
                "Backtest range contains no weekdays."
            )

        report = BacktestReport(
            start_date=start_date,
            end_date=end_date,
            data_feed=data_feed,
            slippage_bps=slippage_bps,
            commission_per_share=commission_per_share,
            train_fraction=train_fraction,
        )

        benchmark_start = (
            start - timedelta(days=60)
        ).isoformat()
        try:
            benchmark_bars = (
                self.alpaca.get_historical_daily_bars(
                    symbols_csv="SPY,QQQ",
                    start_date=benchmark_start,
                    end_date=end_date,
                    feed=data_feed,
                )
            )
            regimes = market_regimes_by_date(
                benchmark_bars,
                dates,
            )
        except Exception as error:
            print(
                "Market-regime data unavailable; "
                f"continuing without it: {error}"
            )
            regimes = {}

        print()
        print("===================================")
        print(" Multi-Day Historical Backtest")
        print("===================================")
        print(
            f"Date range: {start_date} to {end_date}"
        )
        print(f"Market-data feed: {data_feed.upper()}")
        print(
            "Execution assumptions: "
            f"{slippage_bps:.2f} bps slippage per side, "
            f"${commission_per_share:.4f} commission "
            "per share per side"
        )
        print(
            "READ-ONLY MODE: Google Sheets, dashboard "
            "uploads, Orders, and trading are disabled."
        )

        for trading_date in dates:
            date_str = trading_date.isoformat()

            try:
                with redirect_stdout(StringIO()):
                    session = self.run_replay(
                        date_str=date_str,
                        speed=0,
                        publish_dashboard=False,
                        data_feed=data_feed,
                        slippage_bps=slippage_bps,
                        commission_per_share=(
                            commission_per_share
                        ),
                    )
            except Exception as error:
                report.add_failure(date_str, error)
                print(
                    f"{date_str}: FAILED - {error}"
                )
                continue

            session.summary.market_regimes = regimes.get(
                date_str,
                {},
            )
            report.add_session(session)
            metrics = report.metrics_for([
                record
                for record in report.records
                if record.date == date_str
            ])

            print(
                f"{date_str}: "
                f"{metrics.invest_signals} signals, "
                f"{metrics.wins} wins, "
                f"{metrics.losses} losses, "
                f"{metrics.unresolved} unresolved, "
                f"{metrics.no_entry} no entry, "
                f"{metrics.incomplete_ticker_days} "
                "incomplete ticker-days"
            )

        report.print_summary()
        (
            detail_path,
            summary_path,
            missing_path,
            robustness_path,
            atr_path,
            split_path,
        ) = report.write_csv(output_directory)

        print()
        print(f"Detailed results: {detail_path}")
        print(f"Summary results: {summary_path}")
        print(
            f"Missing-bar diagnostics: {missing_path}"
        )
        print(
            f"Filter comparisons: {robustness_path}"
        )
        print(f"ATR diagnostics: {atr_path}")
        print(
            f"Chronological train/test: {split_path}"
        )

        return report

    def run_strategy_test(self) -> None:
        test_date = "2026-07-23"

        print()
        print(f"Testing strategy for {test_date}...")

        self.calculate_strategy(test_date)

        print()
        print("===== STRATEGY RESULTS =====")

        for stock in self.stocks.values():
            if stock.opening_bar is None:
                print(f"{stock.symbol}: no opening bar")
                continue

            if stock.atr is None:
                print(f"{stock.symbol}: insufficient ATR data")
                continue

            print()
            print(f"Symbol: {stock.symbol}")
            print(f"ATR: {stock.atr:.4f}")
            print(f"Opening range: {stock.candle_range:.4f}")
            print(f"ATR threshold: {stock.atr_threshold:.4f}")
            print(
                "Manipulation:",
                "YES" if stock.is_manipulation else "NO",
            )
            print(
                "Red candle:",
                "YES" if stock.is_red else "NO",
            )
            print(f"Signal: {stock.signal}")
            print(f"Limit buy: {stock.limit_buy:.4f}")
            print(f"Limit sell: {stock.limit_sell:.4f}")
            print(f"Stop loss: {stock.stop_loss:.4f}")
            print(
                "Trading stop loss:",
                f"{stock.trading_stop_loss:.4f}",
            )
            print(f"Proximity: {stock.proximity}")

        print()
        print("Strategy test completed.")

    def calculate_strategy(
            self,
            date_str: str,
    ) -> None:
        opening_bars = self.alpaca.get_opening_15min_bars(
            symbols_csv=self.symbols_csv,
            date_str=date_str,
        )

        atrs = self.alpaca.get_previous_day_ranges_all(
            symbols_csv=self.symbols_csv,
            date_str=date_str,
        )

        for symbol, stock in self.stocks.items():
            opening_bar = opening_bars.get(symbol)
            atr = atrs.get(symbol)

            stock.opening_bar = opening_bar
            stock.atr = atr

            if opening_bar is None or atr is None:
                stock.signal = "NO INVEST"

                print(
                    f"{symbol}: strategy skipped because "
                    "valid opening-bar or ATR data was unavailable."
                )
                continue

            try:
                self.strategy.evaluate(
                    stock=stock,
                    opening_bar=opening_bar,
                    atr=atr,
                )

            except Exception as error:
                stock.signal = "NO INVEST"

                print(
                    f"{symbol}: strategy evaluation failed: "
                    f"{error}"
                )

    def run_strategy_and_write(
            self,
            date_str: str | None = None,
    ) -> None:
        if date_str is None:
            eastern = ZoneInfo("America/New_York")
            date_str = datetime.now(eastern).strftime(
                "%Y-%m-%d"
            )

        print()
        print(f"Running strategy for {date_str}...")

        self.calculate_strategy(date_str)

        invest_symbols = [
            stock.symbol
            for stock in self.stocks.values()
            if stock.signal == "INVEST"
        ]

        print(
            "INVEST signals:",
            ", ".join(invest_symbols)
            if invest_symbols
            else "None",
        )

        self.initialise_sheets()

        write_errors = []

        try:
            self.sheets.write_strategy_results(
                date_str=date_str,
                stocks=self.stocks,
            )

        except Exception as error:
            write_errors.append(
                f"Invest sheet: {error}"
            )
            print(
                "Invest sheet write failed. "
                f"Error: {error}"
            )

        print()
        print("Preparing Webull order previews...")

        try:
            preview_service = WebullPreviewService()
            preview_results = (
                preview_service.prepare_previews(
                    stocks=self.stocks,
                )
            )

            if not preview_results:
                print(
                    "No Webull previews were generated."
                )

            for preview in preview_results:
                symbol = preview["symbol"]
                status = preview["status"]

                if status == "PREVIEW READY":
                    print(
                        f"{symbol}: PREVIEW READY · "
                        f"{preview['quantity']} shares · "
                        f"limit ${preview['limitBuy']:.4f} · "
                        f"target ${preview['target']:.4f} · "
                        "trading stop "
                        f"${preview['tradingStopLoss']:.4f} · "
                        "estimated cost "
                        f"${preview['estimatedCost']:.2f} · "
                        "fee "
                        f"${preview['estimatedTransactionFee']:.2f} · "
                        "NOT SUBMITTED"
                    )
                else:
                    print(
                        f"{symbol}: PREVIEW FAILED · "
                        f"{preview.get('error', 'Unknown error')}"
                    )

        except Exception as error:
            print(
                "Webull preview preparation failed. "
                "Strategy and Sheets results were preserved."
            )
            print(f"Webull preview error: {error}")


        try:
            self.sheets.write_orders(
                date_str=date_str,
                stocks=self.stocks,
            )

        except Exception as error:
            write_errors.append(
                f"Orders sheet: {error}"
            )
            print(
                "Orders sheet write failed. "
                f"Error: {error}"
            )

        if write_errors:
            raise RuntimeError(
                "One or more strategy writes failed: "
                + " | ".join(write_errors)
            )

        print("Strategy results written successfully.")


    def run_production(self) -> None:
        eastern = ZoneInfo("America/New_York")
        now = datetime.now(eastern)

        date_str = now.strftime("%Y-%m-%d")

        if now.weekday() >= 5:
            print()
            print("The market is closed today.")
            print("Production mode was not started.")
            return

        market_open = datetime.combine(
            now.date(),
            time(hour=9, minute=30),
            tzinfo=eastern,
        )

        strategy_time = datetime.combine(
            now.date(),
            time(hour=9, minute=45),
            tzinfo=eastern,
        ) + timedelta(seconds=15)

        production_cutoff = datetime.combine(
            now.date(),
            time(hour=10),
            tzinfo=eastern,
        )

        print()
        print("===================================")
        print(" Production Trading Mode")
        print("===================================")
        print(f"Trading date: {date_str}")

        if now >= production_cutoff:
            print()
            print(
                "The 10:00 New York production cutoff "
                "has passed."
            )
            print(
                "Tracking, strategy calculation, and "
                "spreadsheet writes were not started."
            )
            return

        if now < market_open:
            wait_seconds = (
                    market_open - now
            ).total_seconds()

            print(
                "Waiting for market open at "
                "09:30 New York time..."
            )

            time_module.sleep(wait_seconds)

        elif now >= strategy_time:
            print()
            print("The opening tracking window has ended.")
            print("Skipping live tracking.")
            print("Running the strategy immediately...")

            self.run_strategy_and_write(
                date_str=date_str
            )

            print()
            print("Production workflow completed.")
            return

        else:
            print()
            print("The opening window has already started.")
            print("Starting the tracker now...")

        self.run_live_tracker()

        now = datetime.now(eastern)

        remaining_seconds = (
                strategy_time - now
        ).total_seconds()

        if remaining_seconds > 0:
            print()
            print(
                "Waiting for Alpaca to complete "
                "the opening 15-minute candle..."
            )

            time_module.sleep(remaining_seconds)

        print()
        print("Opening tracking window completed.")
        print("Calculating strategy signals...")

        self.run_strategy_and_write(
            date_str=date_str
        )

        print()
        print("Production workflow completed.")
