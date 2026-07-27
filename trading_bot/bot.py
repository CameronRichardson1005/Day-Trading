import time as time_module

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .alpaca_client import AlpacaClient
from .config import CANDIDATE_TICKERS, TICKERS
from .models import Stock
from .replay import HistoricalReplay
from .scanner import StockScanner
from .sheets_client import SheetsClient
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

        self.sheets = None
        self.tracker = None

    def refresh_symbols_for_date(
            self,
            date_str: str,
    ) -> list[str]:
        self.scanner_statistics = None

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
                )
            )

            selected_symbols = (
                self.scanner.select_symbols(
                    statistics
                )
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

    def initialise_sheets(self) -> None:
        if self.sheets is None:
            self.sheets = SheetsClient()

        if self.tracker is None:
            self.tracker = MinuteTracker(
                alpaca=self.alpaca,
                sheets=self.sheets,
                stocks=self.stocks,
                symbols_csv=self.symbols_csv,
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

    def run_live_tracker(self) -> None:
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
            time(hour=9, minute=45),
            tzinfo=eastern,
        )

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
        self.initialise_sheets()

        if self.scanner_statistics is not None:
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
            market_end_eastern.strftime("%H:%M"),
            "New York time",
        )

        self.tracker.track_window(
            date_str=date_str,
            window_start=window_start,
            window_end=window_end,
        )

    def run_replay(
            self,
            date_str: str,
            speed: float = 60.0,
    ) -> None:
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
        print(
            "READ-ONLY MODE: Google Sheets, Orders, "
            "and trading are disabled."
        )

        self.refresh_symbols_for_date(date_str)

        bars_by_symbol = (
            self.alpaca.get_historical_1min_bars(
                symbols_csv=self.symbols_csv,
                start_iso=window_start.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                end_iso=window_end.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            )
        )

        atrs = self.alpaca.get_previous_day_ranges_all(
            symbols_csv=self.symbols_csv,
            date_str=date_str,
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