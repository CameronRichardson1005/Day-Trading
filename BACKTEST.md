# Multi-day backtesting

Run a date range from the project directory:

```bash
python main.py backtest 2026-07-13 2026-07-24
```

Use consolidated SIP data for a historical comparison:

```bash
python main.py backtest 2026-07-13 2026-07-24 --feed sip
```

IEX remains the default. The selected feed is used consistently for the
scanner, ATR bars, opening-minute bars, and post-09:45 outcome bars. A SIP
authorization error is reported as a failed session; the bot never silently
falls back to IEX.

The backtest:

- reuses the same scanner, ATR, strategy, and outcome logic as single-day replay;
- evaluates historical losses against the strategy's original
  `trading_stop_loss` level (the wider executable stop), while retaining both
  stop levels in the detailed report;
- processes NYSE sessions in the inclusive range and skips exchange holidays;
- continues if one date fails;
- closes entered positions at the final available session price when neither
  target nor stop is reached;
- diagnoses daily-bar coverage for every ATR calculation;
- compares baseline signals in SPY and QQQ bull/bear regimes using only data
  available before each tested session;
- creates a chronological training/test comparison without mixing dates;
- does not write to Google Sheets;
- does not upload sessions to the dashboard;
- cannot create, modify, or cancel orders.

Six files are written to `reports/`:

- `backtest_START_to_END_details.csv` contains every ticker-day;
- `backtest_START_to_END_summary.csv` contains overall and per-ticker metrics.
- `backtest_START_to_END_missing_bars.csv` contains each exact absent opening
  timestamp and its feed-level classification.
- `backtest_START_to_END_robustness.csv` compares the baseline with
  leave-one-ticker-out, combined candidate, stricter signal, and market-regime
  filters.
- `backtest_START_to_END_atr_diagnostics.csv` records daily-bar counts and the
  exact ATR availability status for every ticker-day.
- `backtest_START_to_END_train_test.csv` evaluates the same variants on an
  earlier training period and a later untouched test period. The best eligible
  training variant is marked, but is not applied to the strategy.

When a paginated request completes but a minute has no valid aggregate bar,
the diagnostic is `NO_VALID_IEX_BAR_RETURNED` or
`NO_VALID_SIP_BAR_RETURNED`. A request or authorization failure is recorded
separately as a failed session.

Use another output directory when needed:

```bash
python main.py backtest 2026-07-13 2026-07-24 --output my-reports
```

For the larger validation sample, run roughly five months of history:

```bash
python main.py backtest 2026-03-09 2026-07-24 --feed sip
```

Add conservative execution assumptions without changing strategy rules:

```bash
python main.py backtest 2026-03-02 2026-07-24 \
  --feed sip \
  --slippage-bps 5 \
  --commission-per-share 0.005 \
  --train-fraction 0.70 \
  --output reports/sip-research-v2
```

Slippage is applied against the trade on both entry and exit. Commission is
also applied per share on both sides. Defaults are zero so older baseline
results remain directly reproducible.

The robustness variants are exploratory diagnostics. Do not adopt the
best-looking filter until it remains better on a later, untouched date range.

## Metric definitions

- Win rate uses closed trades only: wins divided by wins plus losses.
- Average closed return is the mean percentage return of wins and losses.
- Total equal-weight return is the sum of closed-trade percentage returns. It
  assumes equal weight per signal and is not an account-level portfolio return.
- Profit factor is gross positive percentage return divided by the absolute
  gross negative percentage return.
- Maximum drawdown is the largest peak-to-trough decline in cumulative,
  equal-weight percentage-return points.
- Entered trades that do not reach their target or stop are marked to the final
  available session close with `exit_reason=EOD`.
- `NO ENTRY` is reported separately because the limit-buy price was never
  reached.

Single-day replay remains available:

```bash
python main.py replay 2026-07-23 --speed 0
```

Single-day SIP replay:

```bash
python main.py replay 2026-07-23 --speed 0 --feed sip
```
