from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class WebullPreviewStoreError(RuntimeError):
    pass


class WebullPreviewStore:
    """
    Local persistence for redacted Webull preview proposals.

    This store never contains approval tokens, account IDs,
    credentials, broker responses, or order-submission data.
    """

    def __init__(
        self,
        path: Path | str = (
            "state/webull_preview_proposals.json"
        ),
    ) -> None:
        self.path = Path(path)
        self.temp_path = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

    @staticmethod
    def _validate_preview(
        preview: Any,
    ) -> dict[str, Any]:
        if not isinstance(preview, dict):
            raise WebullPreviewStoreError(
                "Preview record must be an object."
            )

        required = {
            "symbol",
            "quantity",
            "limitPrice",
            "proposedExposure",
            "status",
            "createdAt",
        }

        unknown = set(preview) - required

        if unknown:
            raise WebullPreviewStoreError(
                "Preview record contains unsupported fields: "
                + ", ".join(sorted(unknown))
            )

        missing = required - set(preview)

        if missing:
            raise WebullPreviewStoreError(
                "Preview record is missing fields: "
                + ", ".join(sorted(missing))
            )

        symbol = str(preview["symbol"]).strip().upper()
        status = str(preview["status"]).strip().upper()

        try:
            quantity = int(preview["quantity"])
            limit_price = float(preview["limitPrice"])
            proposed_exposure = float(
                preview["proposedExposure"]
            )
        except (TypeError, ValueError) as error:
            raise WebullPreviewStoreError(
                "Preview numeric fields are invalid."
            ) from error

        if not symbol:
            raise WebullPreviewStoreError(
                "Preview symbol is required."
            )

        if status != "PREVIEW READY":
            raise WebullPreviewStoreError(
                "Only PREVIEW READY records may be stored."
            )

        if quantity <= 0:
            raise WebullPreviewStoreError(
                "Preview quantity must be positive."
            )

        if limit_price <= 0:
            raise WebullPreviewStoreError(
                "Preview limit price must be positive."
            )

        expected_exposure = round(
            quantity * limit_price,
            2,
        )

        if round(proposed_exposure, 2) != expected_exposure:
            raise WebullPreviewStoreError(
                "Preview proposed exposure does not match "
                "quantity multiplied by limit price."
            )

        created_at = preview["createdAt"]

        if not isinstance(created_at, str):
            raise WebullPreviewStoreError(
                "Preview createdAt must be a string."
            )

        try:
            parsed = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )
        except ValueError as error:
            raise WebullPreviewStoreError(
                "Preview createdAt is invalid."
            ) from error

        if parsed.tzinfo is None:
            raise WebullPreviewStoreError(
                "Preview createdAt must include a timezone."
            )

        return {
            "symbol": symbol,
            "quantity": quantity,
            "limitPrice": round(limit_price, 4),
            "proposedExposure": expected_exposure,
            "status": "PREVIEW READY",
            "createdAt": (
                parsed.astimezone(UTC)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            ),
        }

    def save_previews(
        self,
        previews: list[dict[str, Any]],
    ) -> None:
        validated = [
            self._validate_preview(preview)
            for preview in previews
        ]

        payload = {
            "version": 1,
            "previews": sorted(
                validated,
                key=lambda item: item["symbol"],
            ),
        }

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        encoded = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n"

        try:
            self.temp_path.write_text(
                encoded,
                encoding="utf-8",
            )
            os.chmod(self.temp_path, 0o600)
            os.replace(
                self.temp_path,
                self.path,
            )
        except OSError as error:
            raise WebullPreviewStoreError(
                "Preview store could not be written."
            ) from error

    def load_preview(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        if not self.path.exists():
            return None

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise WebullPreviewStoreError(
                "Preview store could not be read."
            ) from error

        if not isinstance(payload, dict):
            raise WebullPreviewStoreError(
                "Preview store root must be an object."
            )

        if payload.get("version") != 1:
            raise WebullPreviewStoreError(
                "Unsupported preview store version."
            )

        previews = payload.get("previews")

        if not isinstance(previews, list):
            raise WebullPreviewStoreError(
                "Preview store previews must be a list."
            )

        normalized_symbol = symbol.strip().upper()

        for raw_preview in previews:
            preview = self._validate_preview(
                raw_preview
            )

            if preview["symbol"] == normalized_symbol:
                return preview

        return None
