import gspread
from google.oauth2.service_account import Credentials

from .config import CREDS_FILE, SCOPES, SHEET_NAME

WHITE = {
    "red": 1,
    "green": 1,
    "blue": 1,
}

LIGHT_BLUE = {
    "red": 0.68,
    "green": 0.85,
    "blue": 0.9,
}

LIGHT_RED = {
    "red": 1,
    "green": 0.75,
    "blue": 0.75,
}

LIGHT_GREEN = {
    "red": 0.78,
    "green": 0.93,
    "blue": 0.78,
}

class SheetsClient:
    def __init__(self) -> None:
        self.credentials = Credentials.from_service_account_file(
            CREDS_FILE,
            scopes=SCOPES,
        )

        self.google_client = gspread.authorize(self.credentials)
        self.spreadsheet = self.google_client.open(SHEET_NAME)

    def get_or_create_worksheet(
        self,
        title: str,
        rows: int = 100,
        cols: int = 20,
    ):
        try:
            return self.spreadsheet.worksheet(title)

        except gspread.exceptions.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(
                title=title,
                rows=rows,
                cols=cols,
            )

    def test_connection(self) -> list[str]:
        worksheets = self.spreadsheet.worksheets()

        return [
            worksheet.title
            for worksheet in worksheets
        ]

    def update_tracking_minute(
            self,
            worksheet,
            updates: list[dict],
    ) -> None:
        """
        Write all stock values and formatting for one minute using
        one values request and one formatting request.
        """
        value_updates = []
        format_requests = []

        sheet_id = worksheet.id

        for update in updates:
            row_number = update["row"]
            row_index = row_number - 1

            value_updates.append(
                {
                    "range": f"C{row_number}:F{row_number}",
                    "values": [
                        [
                            update["running_high"],
                            update["running_low"],
                            update["time_label"],
                            update["candle_color"],
                        ]
                    ],
                }
            )

            format_requests.extend(
                [
                    self._background_request(
                        sheet_id=sheet_id,
                        row_index=row_index,
                        column_index=2,
                        color=(
                            LIGHT_BLUE
                            if update["new_high"]
                            else WHITE
                        ),
                    ),
                    self._background_request(
                        sheet_id=sheet_id,
                        row_index=row_index,
                        column_index=3,
                        color=(
                            LIGHT_RED
                            if update["new_low"]
                            else WHITE
                        ),
                    ),
                    self._background_request(
                        sheet_id=sheet_id,
                        row_index=row_index,
                        column_index=5,
                        color=(
                            LIGHT_GREEN
                            if update["candle_color"] == "GREEN"
                            else WHITE
                        ),
                    ),
                ]
            )

        if value_updates:
            worksheet.batch_update(value_updates)

        if format_requests:
            self.spreadsheet.batch_update(
                {
                    "requests": format_requests,
                }
            )

    @staticmethod
    def _background_request(
            sheet_id: int,
            row_index: int,
            column_index: int,
            color: dict,
    ) -> dict:
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": column_index,
                    "endColumnIndex": column_index + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": color,
                    }
                },
                "fields": (
                    "userEnteredFormat.backgroundColor"
                ),
            }
        }

    def write_strategy_results(
            self,
            date_str: str,
            stocks: dict,
    ) -> None:
        invest_columns = [
            "Date",
            "Symbol",
            "Open",
            "High",
            "Low",
            "Close",
            "Prev Day Range (ATR)",
            "ATR x 0.25",
            "Candle Range",
            "Manipulation Candle",
            "Red Candle",
            "Signal",
            "Limit Buy",
            "Limit Sell",
            "Stop Loss",
            "Trading Stop Loss",
            "Proximity to High/Low",
        ]

        worksheet = self.get_or_create_worksheet(
            title="Invest",
            rows=100,
            cols=len(invest_columns),
        )

        existing_values = worksheet.get_all_values()

        if (
                not existing_values
                or existing_values[0] != invest_columns
        ):
            worksheet.update(
                values=[invest_columns],
                range_name="A1:Q1",
            )

        rows_to_append = []

        for stock in stocks.values():
            if stock.opening_bar is None or stock.atr is None:
                rows_to_append.append(
                    [
                        date_str,
                        stock.symbol,
                        "No data",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                continue

            opening_bar = stock.opening_bar

            rows_to_append.append(
                [
                    date_str,
                    stock.symbol,
                    opening_bar["o"],
                    opening_bar["h"],
                    opening_bar["l"],
                    opening_bar["c"],
                    round(stock.atr, 4),
                    round(stock.atr_threshold, 4),
                    round(stock.candle_range, 4),
                    "YES" if stock.is_manipulation else "NO",
                    "YES" if stock.is_red else "NO",
                    stock.signal,
                    round(stock.limit_buy, 4),
                    round(stock.limit_sell, 4),
                    round(stock.stop_loss, 4),
                    round(stock.trading_stop_loss, 4),
                    stock.proximity,
                ]
            )

        if rows_to_append:
            worksheet.append_rows(
                rows_to_append,
                value_input_option="USER_ENTERED",
            )

    def write_orders(
            self,
            date_str: str,
            stocks: dict,
    ) -> None:
        order_columns = [
            "Date",
            "Symbol",
            "Limit Buy",
            "Limit Sell",
            "Trading Stop Loss",
        ]

        worksheet = self.get_or_create_worksheet(
            title="Orders",
            rows=100,
            cols=len(order_columns),
        )

        existing_values = worksheet.get_all_values()

        if (
                not existing_values
                or existing_values[0] != order_columns
        ):
            worksheet.update(
                values=[order_columns],
                range_name="A1:E1",
            )

        order_rows = []

        for stock in stocks.values():
            if stock.signal != "INVEST":
                continue

            order_rows.append(
                [
                    date_str,
                    stock.symbol,
                    round(stock.limit_buy, 4),
                    round(stock.limit_sell, 4),
                    round(stock.trading_stop_loss, 4),
                ]
            )

        if order_rows:
            worksheet.append_rows(
                order_rows,
                value_input_option="USER_ENTERED",
            )

            print(
                f"{len(order_rows)} order(s) written "
                "to the Orders sheet."
            )
        else:
            print("No INVEST orders generated.")