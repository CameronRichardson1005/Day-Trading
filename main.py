import sys

from trading_bot.bot import TradingBot


def main() -> None:
    bot = TradingBot()

    mode = (
        sys.argv[1].lower()
        if len(sys.argv) > 1
        else "test"
    )

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


if __name__ == "__main__":
    main()