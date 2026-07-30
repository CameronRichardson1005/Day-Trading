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
