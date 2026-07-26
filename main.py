import logging
import sys

from trading_bot.bot import TradingBot
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

        elif mode == "production":
            bot.run_production()

        else:
            print(f"Unknown mode: {mode}")
            print(
                "Available modes: "
                "test, live, strategy, write, production"
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