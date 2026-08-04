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


    @staticmethod
    def _column_name(column_number: int) -> str:
        """
        Convert a one-based column number into a Google Sheets
        column name.
        """
        result = ""
        number = column_number

        while number:
            number, remainder = divmod(number - 1, 26)
            result = chr(65 + remainder) + result

        return result

    @staticmethod
    def _status_colour(value: str) -> dict | None:
        normalised = str(value).strip().upper()

        green_values = {
            "INVEST",
            "SELECTED",
            "PREVIEW READY",
            "READY",
            "COMPLETE",
            "COMPLETED",
            "YES",
            "GREEN",
            "PASSED",
            "SUCCESS",
        }

        red_values = {
            "NO INVEST",
            "FAILED",
            "ERROR",
            "RED",
            "INCOMPLETE",
        }

        amber_values = {
            "NO",
            "NOT SUBMITTED",
            "NOT PREVIEWED",
            "ELIGIBLE - LIMIT REACHED",
            "PARTIAL",
            "WARNING",
        }

        if normalised in green_values:
            return {
                "red": 0.82,
                "green": 0.94,
                "blue": 0.84,
            }

        if normalised in red_values:
            return {
                "red": 0.98,
                "green": 0.82,
                "blue": 0.82,
            }

        if normalised in amber_values:
            return {
                "red": 1.0,
                "green": 0.93,
                "blue": 0.72,
            }

        if (
            "EXCLUDED" in normalised
            or "LOW IEX RELIABILITY" in normalised
        ):
            return {
                "red": 0.98,
                "green": 0.82,
                "blue": 0.82,
            }

        return None

    def format_worksheet(self, worksheet) -> None:
        """
        Apply consistent professional formatting to a worksheet.

        This does not delete, rename, or replace any data.
        """
        values = worksheet.get_all_values()

        if not values:
            return

        columns = values[0]
        row_count = max(len(values), 2)
        column_count = max(len(columns), 1)
        sheet_id = worksheet.id

        header_background = {
            "red": 0.09,
            "green": 0.20,
            "blue": 0.33,
        }

        body_background = {
            "red": 1.0,
            "green": 1.0,
            "blue": 1.0,
        }

        border_colour = {
            "red": 0.80,
            "green": 0.83,
            "blue": 0.87,
        }

        requests = [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {
                            "frozenRowCount": 1,
                        },
                    },
                    "fields": (
                        "gridProperties.frozenRowCount"
                    ),
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": column_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": header_background,
                            "textFormat": {
                                "foregroundColor": {
                                    "red": 1,
                                    "green": 1,
                                    "blue": 1,
                                },
                                "bold": True,
                                "fontSize": 10,
                            },
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE",
                            "wrapStrategy": "WRAP",
                            "borders": {
                                "bottom": {
                                    "style": "SOLID_MEDIUM",
                                    "color": border_colour,
                                }
                            },
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": row_count,
                        "startColumnIndex": 0,
                        "endColumnIndex": column_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": body_background,
                            "verticalAlignment": "MIDDLE",
                            "wrapStrategy": "WRAP",
                            "textFormat": {
                                "fontSize": 10,
                            },
                            "borders": {
                                "bottom": {
                                    "style": "SOLID",
                                    "color": border_colour,
                                }
                            },
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": column_count,
                    }
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {
                        "pixelSize": 38,
                    },
                    "fields": "pixelSize",
                }
            },
        ]

        currency_four_decimals = {
            "Open",
            "High",
            "Low",
            "Close",
            "Average Price",
            "Average Range",
            "Prev Day Range (ATR)",
            "ATR x 0.25",
            "Candle Range",
            "Limit Buy",
            "Limit Sell",
            "Stop Loss",
            "Trading Stop Loss",
            "Running High",
            "Running Low",
            "VWAP",
        }

        currency_two_decimals = {
            "Estimated Cost",
            "Estimated Fee",
        }

        integer_columns = {
            "Valid Bars",
            "Average Volume",
            "Volume",
            "Trade Count",
            "Quantity",
            "Scanner Rows",
            "Selected Symbols",
            "Strategy Rows",
            "Invest Signals",
            "Order Previews",
            "Orders Submitted",
        }

        percentage_columns = {
            "Average Range %",
            "Reliability",
            "Completeness",
        }

        date_columns = {
            "Date",
        }

        time_columns = {
            "Last Update Time",
            "Timestamp UTC",
            "Timestamp ET",
            "Completed At",
            "Last Updated",
        }

        left_aligned_columns = {
            "Decision",
            "Proximity to High/Low",
        }

        for index, column in enumerate(columns):
            column_range = {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": row_count,
                "startColumnIndex": index,
                "endColumnIndex": index + 1,
            }

            if column in currency_four_decimals:
                number_format = {
                    "type": "CURRENCY",
                    "pattern": "$#,##0.0000",
                }
            elif column in currency_two_decimals:
                number_format = {
                    "type": "CURRENCY",
                    "pattern": "$#,##0.00",
                }
            elif column in integer_columns:
                number_format = {
                    "type": "NUMBER",
                    "pattern": "#,##0",
                }
            elif column in percentage_columns:
                number_format = {
                    "type": "NUMBER",
                    "pattern": '0.00"%"',
                }
            elif column in date_columns:
                number_format = {
                    "type": "DATE",
                    "pattern": "yyyy-mm-dd",
                }
            elif column in time_columns:
                number_format = {
                    "type": "DATE_TIME",
                    "pattern": "yyyy-mm-dd hh:mm:ss",
                }
            else:
                number_format = None

            if number_format is not None:
                requests.append(
                    {
                        "repeatCell": {
                            "range": column_range,
                            "cell": {
                                "userEnteredFormat": {
                                    "numberFormat": number_format,
                                }
                            },
                            "fields": (
                                "userEnteredFormat.numberFormat"
                            ),
                        }
                    }
                )

            alignment = (
                "LEFT"
                if column in left_aligned_columns
                else "CENTER"
            )

            requests.append(
                {
                    "repeatCell": {
                        "range": column_range,
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": alignment,
                            }
                        },
                        "fields": (
                            "userEnteredFormat."
                            "horizontalAlignment"
                        ),
                    }
                }
            )

        for row_index, row in enumerate(values[1:], start=1):
            for column_index, value in enumerate(row):
                colour = self._status_colour(value)

                if colour is None:
                    continue

                requests.append(
                    {
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
                                    "backgroundColor": colour,
                                    "textFormat": {
                                        "bold": True,
                                    },
                                    "horizontalAlignment": "CENTER",
                                }
                            },
                            "fields": (
                                "userEnteredFormat."
                                "backgroundColor,"
                                "userEnteredFormat."
                                "textFormat.bold,"
                                "userEnteredFormat."
                                "horizontalAlignment"
                            ),
                        }
                    }
                )

        self.spreadsheet.batch_update(
            {
                "requests": requests,
            }
        )

    def format_all_sheets(self) -> None:
        """
        Apply professional formatting to every worksheet in the
        workbook.
        """
        formatted = 0

        for worksheet in self.spreadsheet.worksheets():
            try:
                self.format_worksheet(worksheet)
                formatted += 1
            except Exception as error:
                print(
                    f"Formatting skipped for {worksheet.title}: "
                    f"{error}"
                )

        print(
            f"{formatted} worksheet(s) professionally formatted."
        )

    @staticmethod
    def _sheet_rows_for_date(
        worksheet,
        date_str: str,
    ) -> tuple[list[str], list[list[str]]]:
        values = worksheet.get_all_values()

        if not values:
            return [], []

        columns = values[0]
        rows = [
            row
            for row in values[1:]
            if row and row[0] == date_str
        ]

        return columns, rows

    def write_daily_summary(
        self,
        date_str: str,
    ) -> None:
        """
        Build one permanent summary row for a trading date.
        """
        scanner_rows = []
        strategy_rows = []
        order_rows = []

        try:
            _, scanner_rows = self._sheet_rows_for_date(
                self.spreadsheet.worksheet(
                    "Scanner Dashboard"
                ),
                date_str,
            )
        except gspread.exceptions.WorksheetNotFound:
            pass

        try:
            strategy_columns, strategy_rows = (
                self._sheet_rows_for_date(
                    self.spreadsheet.worksheet("Invest"),
                    date_str,
                )
            )
        except gspread.exceptions.WorksheetNotFound:
            strategy_columns = []

        try:
            order_columns, order_rows = (
                self._sheet_rows_for_date(
                    self.spreadsheet.worksheet("Orders"),
                    date_str,
                )
            )
        except gspread.exceptions.WorksheetNotFound:
            order_columns = []

        selected_count = 0
        for row in scanner_rows:
            if len(row) > 9 and row[9].strip().upper() == "YES":
                selected_count += 1

        signal_index = (
            strategy_columns.index("Signal")
            if "Signal" in strategy_columns
            else -1
        )

        invest_count = sum(
            1
            for row in strategy_rows
            if (
                signal_index >= 0
                and len(row) > signal_index
                and row[signal_index].strip().upper() == "INVEST"
            )
        )

        preview_index = (
            order_columns.index("Webull Preview")
            if "Webull Preview" in order_columns
            else -1
        )

        submitted_index = (
            order_columns.index("Submitted")
            if "Submitted" in order_columns
            else -1
        )

        preview_count = sum(
            1
            for row in order_rows
            if (
                preview_index >= 0
                and len(row) > preview_index
                and row[preview_index].strip().upper()
                == "PREVIEW READY"
            )
        )

        submitted_count = sum(
            1
            for row in order_rows
            if (
                submitted_index >= 0
                and len(row) > submitted_index
                and row[submitted_index].strip().upper()
                in {"YES", "TRUE", "SUBMITTED"}
            )
        )

        from datetime import datetime
        from zoneinfo import ZoneInfo

        completed_at = datetime.now(
            ZoneInfo("America/New_York")
        ).strftime("%Y-%m-%d %H:%M:%S")

        columns = [
            "Date",
            "Scanner Rows",
            "Selected Symbols",
            "Strategy Rows",
            "Invest Signals",
            "Order Previews",
            "Orders Submitted",
            "Last Updated",
            "Status",
        ]

        row = [
            date_str,
            len(scanner_rows),
            selected_count,
            len(strategy_rows),
            invest_count,
            preview_count,
            submitted_count,
            completed_at,
            "COMPLETE",
        ]

        worksheet = self.get_or_create_worksheet(
            title="Daily Summary",
            rows=250,
            cols=len(columns),
        )

        self._replace_date_rows(
            worksheet=worksheet,
            columns=columns,
            date_str=date_str,
            replacement_rows=[row],
            last_column="I",
            sheet_name="Daily Summary",
        )

    def write_production_run(
        self,
        date_str: str,
    ) -> None:
        """
        Store one end-of-day production audit record.
        """
        import os
        from datetime import datetime
        from zoneinfo import ZoneInfo

        completed_at = datetime.now(
            ZoneInfo("America/New_York")
        ).strftime("%Y-%m-%d %H:%M:%S")

        columns = [
            "Date",
            "Completed At",
            "Run Mode",
            "Data Feed",
            "Strategy Status",
            "Sheets Status",
            "Webull Status",
            "Submitted",
            "Overall Status",
        ]

        row = [
            date_str,
            completed_at,
            os.getenv("TRADING_RUN_MODE", "MANUAL"),
            os.getenv("ALPACA_DATA_FEED", "iex").upper(),
            "COMPLETE",
            "COMPLETE",
            (
                "PREVIEW ONLY"
                if os.getenv(
                    "WEBULL_PREVIEW_ENABLED",
                    "false",
                ).lower() == "true"
                else "DISABLED"
            ),
            "NO",
            "COMPLETE",
        ]

        worksheet = self.get_or_create_worksheet(
            title="Production Runs",
            rows=250,
            cols=len(columns),
        )

        self._replace_date_rows(
            worksheet=worksheet,
            columns=columns,
            date_str=date_str,
            replacement_rows=[row],
            last_column="I",
            sheet_name="Production Runs",
        )


    def refresh_today_sheet(
        self,
        date_str: str,
    ) -> None:
        """
        Build a clean user-facing view for one trading date.

        Historical data remains stored in the archive worksheets.
        """
        sections: list[list] = []

        sections.extend(
            [
                ["TRADING DESK — TODAY"],
                ["Trading Date", date_str],
                ["Execution Mode", "WEBULL PREVIEW ONLY"],
                ["Orders Submitted Automatically", "NO"],
                [],
            ]
        )

        try:
            summary_sheet = self.spreadsheet.worksheet(
                "Daily Summary"
            )
            summary_columns, summary_rows = (
                self._sheet_rows_for_date(
                    summary_sheet,
                    date_str,
                )
            )
        except gspread.exceptions.WorksheetNotFound:
            summary_columns = []
            summary_rows = []

        sections.append(["DAILY SUMMARY"])

        if summary_rows:
            summary = summary_rows[-1]

            for index, column in enumerate(summary_columns):
                value = (
                    summary[index]
                    if index < len(summary)
                    else ""
                )
                sections.append([column, value])
        else:
            sections.append(
                ["Status", "No daily summary available"]
            )

        sections.append([])
        sections.append(
            [
                "TODAY'S ORDERS",
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

        order_columns = [
            "Date",
            "Symbol",
            "Limit Buy",
            "Limit Sell",
            "Trading Stop Loss",
            "Webull Preview",
            "Quantity",
            "Estimated Position Value",
            "Maximum Position Value",
            "Sizing Constraint",
            "Estimated Cost",
            "Estimated Fee",
            "Submitted",
        ]

        try:
            orders_sheet = self.spreadsheet.worksheet("Orders")
            existing_columns, order_rows = (
                self._sheet_rows_for_date(
                    orders_sheet,
                    date_str,
                )
            )

            if existing_columns:
                order_columns = existing_columns
        except gspread.exceptions.WorksheetNotFound:
            order_rows = []

        sections.append(order_columns)

        if order_rows:
            sections.extend(order_rows)
        else:
            sections.append(
                [
                    date_str,
                    "No INVEST orders",
                    "",
                    "",
                    "",
                    "NOT PREVIEWED",
                    "",
                    "",
                    "",
                    "NO",
                ]
            )

        sections.append([])
        sections.append(
            [
                "TODAY'S STRATEGY RESULTS",
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
                "",
                "",
            ]
        )

        try:
            invest_sheet = self.spreadsheet.worksheet("Invest")
            invest_columns, invest_rows = (
                self._sheet_rows_for_date(
                    invest_sheet,
                    date_str,
                )
            )
        except gspread.exceptions.WorksheetNotFound:
            invest_columns = []
            invest_rows = []

        if invest_columns:
            sections.append(invest_columns)
            sections.extend(invest_rows)
        else:
            sections.append(
                ["Status", "No strategy results available"]
            )

        maximum_columns = max(
            len(row)
            for row in sections
            if row
        )

        normalised_rows = [
            self._normalise_row(
                row=row,
                column_count=maximum_columns,
            )
            for row in sections
        ]

        worksheet = self.get_or_create_worksheet(
            title="Today",
            rows=max(150, len(normalised_rows) + 20),
            cols=maximum_columns,
        )

        last_column = self._column_name(maximum_columns)

        worksheet.clear()
        worksheet.resize(
            rows=max(150, len(normalised_rows) + 20),
            cols=maximum_columns,
        )
        worksheet.update(
            range_name=(
                f"A1:{last_column}{len(normalised_rows)}"
            ),
            values=normalised_rows,
            value_input_option="USER_ENTERED",
        )

        self.format_worksheet(worksheet)

        print(
            f"Today sheet refreshed for {date_str}."
        )


    @staticmethod
    def _history_sort_key(row: list) -> str:
        """
        Return the Date value used to sort historical rows.

        Dates are stored as YYYY-MM-DD, so descending text order is
        also descending chronological order.
        """
        if not row:
            return ""

        return str(row[0]).strip()

    def sort_history_sheets(self) -> None:
        """
        Sort every historical worksheet newest-date first.

        Only worksheets whose first header is Date are changed.
        User-facing worksheets such as Today are left unchanged.
        """
        excluded_titles = {
            "Today",
            "Dashboard",
        }

        sorted_count = 0

        for worksheet in self.spreadsheet.worksheets():
            if worksheet.title in excluded_titles:
                continue

            values = worksheet.get_all_values()

            if not values:
                continue

            columns = values[0]

            if not columns or columns[0].strip() != "Date":
                continue

            column_count = len(columns)
            dated_rows = []
            undated_rows = []

            for row in values[1:]:
                normalised = self._normalise_row(
                    row=row,
                    column_count=column_count,
                )

                if self._history_sort_key(normalised):
                    dated_rows.append(normalised)
                else:
                    undated_rows.append(normalised)

            dated_rows.sort(
                key=self._history_sort_key,
                reverse=True,
            )

            ordered_rows = [
                *dated_rows,
                *undated_rows,
            ]

            self._rewrite_table(
                worksheet=worksheet,
                columns=columns,
                rows=ordered_rows,
                last_column=self._column_name(column_count),
            )

            sorted_count += 1

        print(
            f"{sorted_count} historical worksheet(s) sorted "
            "newest first."
        )

    def finalise_daily_workbook(
        self,
        date_str: str,
    ) -> None:
        """
        Complete the permanent daily archive and professionally
        format every worksheet.
        """
        self.write_daily_summary(date_str)
        self.write_production_run(date_str)
        self.sort_history_sheets()
        self.refresh_today_sheet(date_str)
        self.format_all_sheets()

        print(
            f"Google Sheets daily archive finalised for "
            f"{date_str}."
        )


    @staticmethod
    def _normalise_bar_timestamp(
        timestamp: str,
    ) -> tuple[str, str]:
        """
        Return UTC and New York timestamp labels for one Alpaca bar.
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        raw = str(timestamp).strip()

        if not raw:
            return "", ""

        parsed = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=ZoneInfo("UTC")
            )

        utc_value = parsed.astimezone(
            ZoneInfo("UTC")
        )
        eastern_value = parsed.astimezone(
            ZoneInfo("America/New_York")
        )

        return (
            utc_value.strftime("%Y-%m-%d %H:%M:%S"),
            eastern_value.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def write_minute_bars_history(
        self,
        date_str: str,
        stocks: dict,
        data_feed: str = "iex",
        source: str = "LIVE",
    ) -> None:
        """
        Store every genuine reconciled one-minute bar permanently.

        Rows for the supplied date are rebuilt from the current
        in-memory bars. All other historical dates are preserved.
        """
        columns = [
            "Date",
            "Symbol",
            "Timestamp UTC",
            "Timestamp ET",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Trade Count",
            "VWAP",
            "Data Feed",
            "Source",
        ]

        worksheet = self.get_or_create_worksheet(
            title="Minute Bars History",
            rows=2000,
            cols=len(columns),
        )

        unique_rows: dict[
            tuple[str, str],
            list,
        ] = {}

        for stock in stocks.values():
            for bar in stock.minute_bars:
                raw_timestamp = str(
                    bar.get("t", "")
                ).strip()

                if not raw_timestamp:
                    continue

                timestamp_utc, timestamp_et = (
                    self._normalise_bar_timestamp(
                        raw_timestamp
                    )
                )

                key = (
                    stock.symbol,
                    timestamp_utc,
                )

                unique_rows[key] = [
                    date_str,
                    stock.symbol,
                    timestamp_utc,
                    timestamp_et,
                    bar.get("o", ""),
                    bar.get("h", ""),
                    bar.get("l", ""),
                    bar.get("c", ""),
                    bar.get("v", ""),
                    bar.get("n", ""),
                    bar.get("vw", ""),
                    data_feed.strip().upper(),
                    source.strip().upper(),
                ]

        history_rows = [
            unique_rows[key]
            for key in sorted(
                unique_rows,
                key=lambda item: (
                    item[0],
                    item[1],
                ),
            )
        ]

        self._replace_date_rows(
            worksheet=worksheet,
            columns=columns,
            date_str=date_str,
            replacement_rows=history_rows,
            last_column="M",
            sheet_name="Minute Bars History",
        )

        print(
            f"{len(history_rows)} genuine minute bar(s) "
            "reconciled in the Minute Bars History sheet."
        )

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
                            "estimatedPositionValue",
                            "",
                        )
                        if stock.webull_preview
                        else ""
                    ),
                    (
                        stock.webull_preview.get(
                            "maxPositionValue",
                            "",
                        )
                        if stock.webull_preview
                        else ""
                    ),
                    (
                        stock.webull_preview.get(
                            "sizingConstraint",
                            "",
                        )
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
            last_column="M",
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
