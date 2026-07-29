import gspread
from google.oauth2.service_account import Credentials

from .config import (
    CREDS_FILE,
    SCOPES,
    SHEETS_REQUEST_TIMEOUT,
    SPREADSHEET_ID,
)

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
        self.google_client.set_timeout(
            SHEETS_REQUEST_TIMEOUT
        )
        self.spreadsheet = (
            self.google_client.open_by_key(
                SPREADSHEET_ID
            )
        )

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
    @staticmethod
    def _validate_header(
        existing_values: list[list[str]],
        expected_columns: list[str],
        sheet_name: str,
    ) -> None:
        if existing_values and existing_values[0] != expected_columns:
            raise RuntimeError(
                f"{sheet_name} has unexpected columns. "
                "The sheet was not modified."
            )

    @staticmethod
    def _normalise_row(
        row: list,
        column_count: int,
    ) -> list:
        normalised = list(row[:column_count])

        if len(normalised) < column_count:
            normalised.extend(
                [""] * (column_count - len(normalised))
            )

        return normalised

    def _rewrite_table(
        self,
        worksheet,
        columns: list[str],
        rows: list[list],
        last_column: str,
    ) -> None:
        existing_row_count = len(worksheet.get_all_values())
        table = [columns, *rows]

        worksheet.update(
            values=table,
            range_name=(
                f"A1:{last_column}{len(table)}"
            ),
            value_input_option="USER_ENTERED",
        )

        if existing_row_count > len(table):
            worksheet.batch_clear(
                [
                    (
                        f"A{len(table) + 1}:"
                        f"{last_column}{existing_row_count}"
                    )
                ]
            )

    def _replace_date_rows(
        self,
        worksheet,
        columns: list[str],
        date_str: str,
        replacement_rows: list[list],
        last_column: str,
        sheet_name: str,
    ) -> None:
        existing_values = worksheet.get_all_values()

        self._validate_header(
            existing_values=existing_values,
            expected_columns=columns,
            sheet_name=sheet_name,
        )

        preserved_rows = []

        for row in existing_values[1:]:
            normalised = self._normalise_row(
                row=row,
                column_count=len(columns),
            )

            if normalised[0] != date_str:
                preserved_rows.append(normalised)

        self._rewrite_table(
            worksheet=worksheet,
            columns=columns,
            rows=[
                *preserved_rows,
                *replacement_rows,
            ],
            last_column=last_column,
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

        strategy_rows = []

        for stock in stocks.values():
            if stock.opening_bar is None or stock.atr is None:
                strategy_rows.append(
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
                        "NO INVEST",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                continue

            opening_bar = stock.opening_bar

            strategy_rows.append(
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

        self._replace_date_rows(
            worksheet=worksheet,
            columns=invest_columns,
            date_str=date_str,
            replacement_rows=strategy_rows,
            last_column="Q",
            sheet_name="Invest",
        )

        print(
            f"{len(strategy_rows)} strategy row(s) reconciled "
            "in the Invest sheet."
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
            "Webull Preview",
            "Quantity",
            "Estimated Cost",
            "Estimated Fee",
            "Submitted",
        ]

        worksheet = self.get_or_create_worksheet(
            title="Orders",
            rows=100,
            cols=len(order_columns),
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
                    (
                        stock.webull_preview.get("status")
                        if stock.webull_preview
                        else "NOT PREVIEWED"
                    ),
                    (
                        stock.webull_preview.get("quantity", "")
                        if stock.webull_preview
                        else ""
                    ),
                    (
                        stock.webull_preview.get(
                            "estimatedCost",
                            "",
                        )
                        if stock.webull_preview
                        else ""
                    ),
                    (
                        stock.webull_preview.get(
                            "estimatedTransactionFee",
                            "",
                        )
                        if stock.webull_preview
                        else ""
                    ),
                    "NO",
                ]
            )

        self._replace_date_rows(
            worksheet=worksheet,
            columns=order_columns,
            date_str=date_str,
            replacement_rows=order_rows,
            last_column="J",
            sheet_name="Orders",
        )

        if order_rows:
            print(
                f"{len(order_rows)} order(s) reconciled "
                "in the Orders sheet."
            )
        else:
            print(
                "No INVEST orders generated. "
                "Existing orders for this date were removed."
            )

    def write_scanner_dashboard(
            self,
            date_str: str,
            statistics,
            selected_symbols,
            scanner,
    ) -> None:
        dashboard_columns = [
            "Date",
            "Symbol",
            "Valid Bars",
            "Average Volume",
            "Average Price",
            "Average Range",
            "Average Range %",
            "Ranking Score",
            "Eligible",
            "Selected",
            "Decision",
        ]

        worksheet = self.get_or_create_worksheet(
            title="Scanner Dashboard",
            rows=100,
            cols=len(dashboard_columns),
        )

        selected_set = set(selected_symbols)
        dashboard_rows = []

        ranked_statistics = sorted(
            statistics,
            key=lambda stats: (
                -stats.ranking_score,
                stats.symbol,
            ),
        )

        for stats in ranked_statistics:
            failures = scanner.eligibility_failures(
                stats
            )
            eligible = not failures
            selected = stats.symbol in selected_set

            if selected:
                decision = "SELECTED"
            elif eligible:
                decision = (
                    "ELIGIBLE - LIMIT REACHED"
                )
            else:
                decision = "; ".join(failures)

            dashboard_rows.append(
                [
                    date_str,
                    stats.symbol,
                    stats.valid_bars,
                    round(stats.avg_volume, 2),
                    round(stats.avg_price, 4),
                    round(stats.avg_range, 4),
                    round(stats.avg_range_pct, 4),
                    round(stats.ranking_score, 4),
                    "YES" if eligible else "NO",
                    "YES" if selected else "NO",
                    decision,
                ]
            )

        self._replace_date_rows(
            worksheet=worksheet,
            columns=dashboard_columns,
            date_str=date_str,
            replacement_rows=dashboard_rows,
            last_column="K",
            sheet_name="Scanner Dashboard",
        )

        print(
            f"{len(dashboard_rows)} scanner row(s) "
            "reconciled in the Scanner Dashboard sheet."
        )
