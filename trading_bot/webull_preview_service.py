from __future__ import annotations

from typing import Any

from .config import WEBULL_PREVIEW_ENABLED
from .models import Stock
from .webull_preview_client import (
    WebullPreviewClient,
)


class WebullPreviewService:
    def __init__(
            self,
            client: WebullPreviewClient
            | None = None,
    ) -> None:
        self.client = (
            client or WebullPreviewClient()
        )

    def prepare_previews(
            self,
            stocks: dict[str, Stock],
    ) -> list[dict[str, Any]]:
        if not WEBULL_PREVIEW_ENABLED:
            print(
                "Webull preview integration is disabled."
            )
            return []

        results: list[dict[str, Any]] = []

        for stock in stocks.values():
            stock.webull_preview = None

            if stock.signal != "INVEST":
                continue

            try:
                request = (
                    self.client.build_request(stock)
                )
                preview = self.client.preview(
                    request
                )
                stock.webull_preview = preview
                results.append(preview)

            except Exception as error:
                failure = {
                    "status": "PREVIEW FAILED",
                    "submitted": False,
                    "symbol": stock.symbol,
                    "error": str(error),
                }
                stock.webull_preview = failure
                results.append(failure)

        return results
