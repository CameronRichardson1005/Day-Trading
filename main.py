import logging
import sys

from trading_bot.bot import TradingBot
from trading_bot.config import MARKET_DATA_FEED
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
                "test, smoke, preflight, live, strategy, "
                "write, replay, backtest, production"
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
