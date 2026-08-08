from types import SimpleNamespace

from trading_bot.sheets_client import SheetsClient


def portfolio():
    return SimpleNamespace(
        starting_cash=10_000.0,
        cash=9_965.0,
        buying_power=9_965.0,
        open_cost_basis=40.0,
        market_value=42.0,
        realized_pnl=5.0,
        unrealized_pnl=2.0,
        total_pnl=7.0,
        equity=10_007.0,
        open_position_count=1,
        closed_position_count=2,
        pending_order_count=1,
        no_entry_count=1,
        overdrawn=False,
    )


def test_write_paper_portfolio_uses_dedicated_sheet():
    client = object.__new__(SheetsClient)

    worksheet = object()
    seen = {}

    def get_or_create_worksheet(
        *,
        title,
        rows,
        cols,
    ):
        seen["title"] = title
        seen["rows"] = rows
        seen["cols"] = cols
        return worksheet

    def replace_date_rows(
        *,
        worksheet,
        columns,
        date_str,
        replacement_rows,
        last_column,
        sheet_name,
    ):
        seen["worksheet"] = worksheet
        seen["columns"] = columns
        seen["date_str"] = date_str
        seen["rows_data"] = replacement_rows
        seen["last_column"] = last_column
        seen["sheet_name"] = sheet_name

    client.get_or_create_worksheet = (
        get_or_create_worksheet
    )
    client._replace_date_rows = replace_date_rows

    client.write_paper_portfolio(
        date_str="2026-08-07",
        portfolio=portfolio(),
    )

    assert seen["title"] == "Paper Portfolio"
    assert seen["sheet_name"] == "Paper Portfolio"
    assert seen["date_str"] == "2026-08-07"
    assert seen["last_column"] == "Q"
    assert len(seen["columns"]) == 17

    row = seen["rows_data"][0]

    assert row[0] == "2026-08-07"
    assert row[1] == 10_000.0
    assert row[2] == 9_965.0
    assert row[3] == 9_965.0
    assert row[4] == 40.0
    assert row[5] == 42.0
    assert row[6] == 5.0
    assert row[7] == 2.0
    assert row[8] == 7.0
    assert row[9] == 10_007.0
    assert row[10] == 1
    assert row[11] == 2
    assert row[12] == 1
    assert row[13] == 1
    assert row[14] == "NO"
    assert row[15] == "YES"
    assert row[16] == "NO"


def test_write_paper_portfolio_marks_overdrawn():
    client = object.__new__(SheetsClient)

    worksheet = object()
    seen = {}

    client.get_or_create_worksheet = (
        lambda **kwargs: worksheet
    )

    def replace_date_rows(**kwargs):
        seen.update(kwargs)

    client._replace_date_rows = replace_date_rows

    report = portfolio()
    report.overdrawn = True

    client.write_paper_portfolio(
        date_str="2026-08-07",
        portfolio=report,
    )

    row = seen["replacement_rows"][0]

    assert row[14] == "YES"
    assert row[15] == "YES"
    assert row[16] == "NO"
