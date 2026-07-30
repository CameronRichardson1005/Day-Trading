from trading_bot.sheets_client import SheetsClient


def test_column_name_conversion():
    assert SheetsClient._column_name(1) == "A"
    assert SheetsClient._column_name(26) == "Z"
    assert SheetsClient._column_name(27) == "AA"
    assert SheetsClient._column_name(52) == "AZ"


def test_status_colours():
    assert SheetsClient._status_colour("INVEST") is not None
    assert SheetsClient._status_colour("NO INVEST") is not None
    assert SheetsClient._status_colour("NOT SUBMITTED") is not None
    assert SheetsClient._status_colour("ordinary text") is None


def test_status_colour_is_case_insensitive():
    assert (
        SheetsClient._status_colour("preview ready")
        == SheetsClient._status_colour("PREVIEW READY")
    )


def test_history_sort_key():
    assert (
        SheetsClient._history_sort_key(
            ["2026-07-30", "OPEN"]
        )
        == "2026-07-30"
    )
    assert SheetsClient._history_sort_key([]) == ""


def test_dates_sort_newest_first():
    rows = [
        ["2026-07-28", "OPEN"],
        ["2026-07-30", "SOFI"],
        ["2026-07-29", "RIVN"],
    ]

    rows.sort(
        key=SheetsClient._history_sort_key,
        reverse=True,
    )

    assert [row[0] for row in rows] == [
        "2026-07-30",
        "2026-07-29",
        "2026-07-28",
    ]
