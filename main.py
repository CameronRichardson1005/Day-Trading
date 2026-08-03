import logging
import sys
from datetime import date

from trading_bot.bot import TradingBot
from trading_bot.config import MARKET_DATA_FEED
from trading_bot.market_calendar import nyse_trading_dates
from trading_bot.utils import setup_logging


def main() -> int:
    log_path = setup_logging()

    print(f"Log file: {log_path}")

    mode = (
        sys.argv[1].lower()
        if len(sys.argv) > 1
        else "test"
    )

    try:
        if mode == "market-day":
            if len(sys.argv) > 3:
                print(
                    "Usage: python main.py market-day "
                    "[YYYY-MM-DD]"
                )
                return 2

            try:
                check_date = (
                    date.fromisoformat(sys.argv[2])
                    if len(sys.argv) == 3
                    else date.today()
                )
            except ValueError:
                print(
                    "Market date must use YYYY-MM-DD."
                )
                return 1

            trading_dates = nyse_trading_dates(
                check_date,
                check_date,
            )

            if trading_dates:
                print(
                    f"NYSE is scheduled to trade on "
                    f"{check_date.isoformat()}."
                )
                return 0

            print(
                f"NYSE is closed on "
                f"{check_date.isoformat()}."
            )
            return 2

        bot = TradingBot()

        if mode == "test":
            bot.run()

        elif mode == "smoke":
            date_str = (
                sys.argv[2]
                if len(sys.argv) > 2
                else None
            )

            succeeded = bot.run_scanner_smoke(
                date_str=date_str
            )

            if not succeeded:
                return 1

        elif mode == "preflight":
            date_str = (
                sys.argv[2]
                if len(sys.argv) > 2
                else None
            )

            succeeded = bot.run_preflight(
                date_str=date_str
            )

            if not succeeded:
                return 1

        elif mode == "live":
            bot.run_live_tracker()

        elif mode == "live-dry-run":
            bot.run_live_tracker(
                write_sheets=False,
                publish_dashboard=False,
            )

        elif mode == "strategy":
            bot.run_strategy_test()

        elif mode == "write":
            date_str = (
                sys.argv[2]
                if len(sys.argv) > 2
                else None
            )

            bot.run_strategy_and_write(
                date_str=date_str
            )

        elif mode == "replay":
            if len(sys.argv) < 3:
                print(
                    "Usage: python main.py replay "
                    "YYYY-MM-DD [--speed NUMBER] "
                    "[--feed iex|sip]"
                )
                return 2

            date_str = sys.argv[2]
            speed = 60.0
            data_feed = MARKET_DATA_FEED
            replay_options = sys.argv[3:]

            if len(replay_options) % 2:
                print(
                    "Usage: python main.py replay "
                    "YYYY-MM-DD [--speed NUMBER] "
                    "[--feed iex|sip]"
                )
                return 2

            for index in range(0, len(replay_options), 2):
                option = replay_options[index]
                value = replay_options[index + 1]

                if option == "--speed":
                    try:
                        speed = float(value)
                    except ValueError:
                        print("Replay speed must be a number.")
                        return 2
                elif option == "--feed":
                    data_feed = value.lower()
                    if data_feed not in {"iex", "sip"}:
                        print("Feed must be 'iex' or 'sip'.")
                        return 2
                else:
                    print(
                        "Usage: python main.py replay "
                        "YYYY-MM-DD [--speed NUMBER] "
                        "[--feed iex|sip]"
                    )
                    return 2

            bot.run_replay(
                date_str=date_str,
                speed=speed,
                data_feed=data_feed,
            )

        elif mode == "fibonacci-paper":
            date_str = None
            output_path = (
                "reports/fibonacci-paper/"
                "fibonacci_paper_ledger.csv"
            )
            data_feed = MARKET_DATA_FEED
            slippage_bps = 15.0

            options_start = 2

            if (
                len(sys.argv) > 2
                and not sys.argv[2].startswith("--")
            ):
                date_str = sys.argv[2]
                options_start = 3

            options = sys.argv[options_start:]

            if len(options) % 2:
                print(
                    "Usage: python main.py "
                    "fibonacci-paper [YYYY-MM-DD] "
                    "[--output FILE] "
                    "[--feed iex|sip] "
                    "[--slippage-bps NUMBER]"
                )
                return 2

            for index in range(0, len(options), 2):
                option = options[index]
                value = options[index + 1]

                if option == "--output":
                    output_path = value

                elif option == "--feed":
                    data_feed = value.lower()

                    if data_feed not in {"iex", "sip"}:
                        print(
                            "Feed must be 'iex' or 'sip'."
                        )
                        return 2

                elif option == "--slippage-bps":
                    try:
                        slippage_bps = float(value)
                    except ValueError:
                        print(
                            "Slippage bps must be a number."
                        )
                        return 2

                    if slippage_bps < 0:
                        print(
                            "Slippage bps cannot be negative."
                        )
                        return 2

                else:
                    print(
                        "Usage: python main.py "
                        "fibonacci-paper [YYYY-MM-DD] "
                        "[--output FILE] "
                        "[--feed iex|sip] "
                        "[--slippage-bps NUMBER]"
                    )
                    return 2

            bot.run_fibonacci_paper(
                date_str=date_str,
                output_path=output_path,
                data_feed=data_feed,
                slippage_bps=slippage_bps,
            )

        elif mode == "fibonacci-retracement":
            if len(sys.argv) < 4:
                print(
                    "Usage: python main.py "
                    "fibonacci-retracement "
                    "START_DATE END_DATE "
                    "[--output DIRECTORY] "
                    "[--feed iex|sip] "
                    "[--slippage-bps NUMBER] "
                    "[--commission-per-share NUMBER] "
                    "[--minimum-impulse-atr NUMBER]"
                )
                return 2

            output_directory = (
                "reports/fibonacci-retracement"
            )
            data_feed = MARKET_DATA_FEED
            slippage_bps = 0.0
            commission_per_share = 0.0
            minimum_impulse_atr = 1.0
            options = sys.argv[4:]

            if len(options) % 2:
                print(
                    "Usage: python main.py "
                    "fibonacci-retracement "
                    "START_DATE END_DATE "
                    "[--output DIRECTORY] "
                    "[--feed iex|sip] "
                    "[--slippage-bps NUMBER] "
                    "[--commission-per-share NUMBER] "
                    "[--minimum-impulse-atr NUMBER]"
                )
                return 2

            for index in range(
                0,
                len(options),
                2,
            ):
                option = options[index]
                value = options[index + 1]

                if option == "--output":
                    output_directory = value

                elif option == "--feed":
                    data_feed = value.lower()

                    if data_feed not in {"iex", "sip"}:
                        print(
                            "Feed must be 'iex' or 'sip'."
                        )
                        return 2

                elif option == "--slippage-bps":
                    try:
                        slippage_bps = float(value)
                    except ValueError:
                        print(
                            "Slippage bps must be a number."
                        )
                        return 2

                elif option == "--commission-per-share":
                    try:
                        commission_per_share = float(
                            value
                        )
                    except ValueError:
                        print(
                            "Commission per share must be "
                            "a number."
                        )
                        return 2

                elif option == "--minimum-impulse-atr":
                    try:
                        minimum_impulse_atr = float(value)
                    except ValueError:
                        print(
                            "Minimum impulse ATR must be "
                            "a number."
                        )
                        return 2

                    if minimum_impulse_atr <= 0:
                        print(
                            "Minimum impulse ATR must be "
                            "positive."
                        )
                        return 2

                else:
                    print(
                        "Usage: python main.py "
                        "fibonacci-retracement "
                        "START_DATE END_DATE "
                        "[--output DIRECTORY] "
                        "[--feed iex|sip] "
                        "[--slippage-bps NUMBER] "
                        "[--commission-per-share NUMBER] "
                    "[--minimum-impulse-atr NUMBER]"
                    )
                    return 2

            bot.run_fibonacci_retracement_research(
                start_date=sys.argv[2],
                end_date=sys.argv[3],
                output_directory=output_directory,
                data_feed=data_feed,
                slippage_bps=slippage_bps,
                commission_per_share=(
                    commission_per_share
                ),
                minimum_impulse_atr=(
                    minimum_impulse_atr
                ),
            )

        elif mode == "fibonacci-research":
            if len(sys.argv) < 4:
                print(
                    "Usage: python main.py fibonacci-research "
                    "START_DATE END_DATE "
                    "[--output DIRECTORY] "
                    "[--feed iex|sip] "
                    "[--slippage-bps NUMBER] "
                    "[--commission-per-share NUMBER]"
                )
                return 2

            output_directory = "reports/fibonacci"
            data_feed = MARKET_DATA_FEED
            slippage_bps = 0.0
            commission_per_share = 0.0
            research_options = sys.argv[4:]

            if len(research_options) % 2:
                print(
                    "Usage: python main.py fibonacci-research "
                    "START_DATE END_DATE "
                    "[--output DIRECTORY] "
                    "[--feed iex|sip] "
                    "[--slippage-bps NUMBER] "
                    "[--commission-per-share NUMBER]"
                )
                return 2

            for index in range(
                0,
                len(research_options),
                2,
            ):
                option = research_options[index]
                value = research_options[index + 1]

                if option == "--output":
                    output_directory = value

                elif option == "--feed":
                    data_feed = value.lower()

                    if data_feed not in {"iex", "sip"}:
                        print(
                            "Feed must be 'iex' or 'sip'."
                        )
                        return 2

                elif option == "--slippage-bps":
                    try:
                        slippage_bps = float(value)
                    except ValueError:
                        print(
                            "Slippage bps must be a number."
                        )
                        return 2

                elif option == "--commission-per-share":
                    try:
                        commission_per_share = float(
                            value
                        )
                    except ValueError:
                        print(
                            "Commission per share must be "
                            "a number."
                        )
                        return 2

                else:
                    print(
                        "Usage: python main.py "
                        "fibonacci-research "
                        "START_DATE END_DATE "
                        "[--output DIRECTORY] "
                        "[--feed iex|sip] "
                        "[--slippage-bps NUMBER] "
                        "[--commission-per-share NUMBER]"
                    )
                    return 2

            bot.run_fibonacci_research(
                start_date=sys.argv[2],
                end_date=sys.argv[3],
                output_directory=output_directory,
                data_feed=data_feed,
                slippage_bps=slippage_bps,
                commission_per_share=(
                    commission_per_share
                ),
            )

        elif mode == "backtest":
            if len(sys.argv) < 4:
                print(
                    "Usage: python main.py backtest "
                    "START_DATE END_DATE "
                    "[--output DIRECTORY] "
                    "[--feed iex|sip] "
                    "[--slippage-bps NUMBER] "
                    "[--commission-per-share NUMBER] "
                    "[--train-fraction NUMBER]"
                )
                return 2

            output_directory = "reports"
            data_feed = MARKET_DATA_FEED
            slippage_bps = 0.0
            commission_per_share = 0.0
            train_fraction = 0.70
            backtest_options = sys.argv[4:]

            if len(backtest_options) % 2:
                print(
                    "Usage: python main.py backtest "
                    "START_DATE END_DATE "
                    "[--output DIRECTORY] "
                    "[--feed iex|sip] "
                    "[--slippage-bps NUMBER] "
                    "[--commission-per-share NUMBER] "
                    "[--train-fraction NUMBER]"
                )
                return 2

            for index in range(0, len(backtest_options), 2):
                option = backtest_options[index]
                value = backtest_options[index + 1]

                if option == "--output":
                    output_directory = value
                elif option == "--feed":
                    data_feed = value.lower()
                    if data_feed not in {"iex", "sip"}:
                        print("Feed must be 'iex' or 'sip'.")
                        return 2
                elif option == "--slippage-bps":
                    try:
                        slippage_bps = float(value)
                    except ValueError:
                        print(
                            "Slippage bps must be a number."
                        )
                        return 2
                elif option == "--commission-per-share":
                    try:
                        commission_per_share = float(value)
                    except ValueError:
                        print(
                            "Commission per share must be "
                            "a number."
                        )
                        return 2
                elif option == "--train-fraction":
                    try:
                        train_fraction = float(value)
                    except ValueError:
                        print(
                            "Train fraction must be a number."
                        )
                        return 2
                else:
                    print(
                        "Usage: python main.py backtest "
                        "START_DATE END_DATE "
                        "[--output DIRECTORY] "
                        "[--feed iex|sip] "
                        "[--slippage-bps NUMBER] "
                        "[--commission-per-share NUMBER] "
                        "[--train-fraction NUMBER]"
                    )
                    return 2

            bot.run_backtest(
                start_date=sys.argv[2],
                end_date=sys.argv[3],
                output_directory=output_directory,
                data_feed=data_feed,
                slippage_bps=slippage_bps,
                commission_per_share=(
                    commission_per_share
                ),
                train_fraction=train_fraction,
            )

        elif mode == "production":
            bot.run_production()

        else:
            print(f"Unknown mode: {mode}")
            print(
                "Available modes: "
                "test, smoke, preflight, live, live-dry-run, strategy, "
                "write, replay, fibonacci-research, "
                "fibonacci-retracement, "
                "backtest, production"
            )
            return 2

    except KeyboardInterrupt:
        print("Bot stopped by user.")
        return 130

    except Exception:
        logging.getLogger(
            "trading_bot"
        ).exception("Bot workflow failed.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
