from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class WebullPaperOrderStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebullPaperOrderRecord:
    paper_order_id: str
    approval_reference: str
    idempotency_key: str
    symbol: str
    side: str
    quantity: int
    limit_price: float
    proposed_exposure: float
    status: str
    created_at: datetime
    submitted_at: datetime
    safety_reason: str

    # Local-paper lifecycle data. These fields never represent
    # an order submitted to Webull.
    target_price: float | None = None
    stop_price: float | None = None
    lifecycle_status: str = "ENTRY PENDING"


class WebullPaperOrderStore:
    """
    Durable local storage for simulated Webull paper orders.

    This store contains no approval tokens, token hashes,
    credentials, account IDs, or raw broker responses.
    """

    def __init__(
        self,
        path: Path | str = (
            "runtime/webull_paper_orders.json"
        ),
    ) -> None:
        self.path = Path(path)
        self.temp_path = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            raise WebullPaperOrderStoreError(
                "Paper-order timestamps must be "
                "timezone-aware."
            )

        return (
            value.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
        *,
        field_name: str,
    ) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise WebullPaperOrderStoreError(
                f"{field_name} is required."
            )

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as error:
            raise WebullPaperOrderStoreError(
                f"{field_name} is invalid."
            ) from error

        if parsed.tzinfo is None:
            raise WebullPaperOrderStoreError(
                f"{field_name} must include a timezone."
            )

        return parsed.astimezone(UTC)

    @staticmethod
    def _validate_record(
        record: WebullPaperOrderRecord,
    ) -> WebullPaperOrderRecord:
        paper_order_id = record.paper_order_id.strip()
        approval_reference = (
            record.approval_reference.strip()
        )
        idempotency_key = record.idempotency_key.strip()
        symbol = record.symbol.strip().upper()
        side = record.side.strip().upper()
        status = record.status.strip().upper()
        safety_reason = record.safety_reason.strip()
        lifecycle_status = (
            record.lifecycle_status.strip().upper()
        )

        if not paper_order_id:
            raise WebullPaperOrderStoreError(
                "paper_order_id is required."
            )

        if not approval_reference:
            raise WebullPaperOrderStoreError(
                "approval_reference is required."
            )

        if not idempotency_key:
            raise WebullPaperOrderStoreError(
                "idempotency_key is required."
            )

        if not symbol:
            raise WebullPaperOrderStoreError(
                "symbol is required."
            )

        if side != "BUY":
            raise WebullPaperOrderStoreError(
                "Only BUY paper orders are supported."
            )

        if record.quantity <= 0:
            raise WebullPaperOrderStoreError(
                "Paper-order quantity must be positive."
            )

        if record.limit_price <= 0:
            raise WebullPaperOrderStoreError(
                "Paper-order limit price must be positive."
            )

        expected_exposure = round(
            record.quantity * record.limit_price,
            2,
        )

        if (
            round(record.proposed_exposure, 2)
            != expected_exposure
        ):
            raise WebullPaperOrderStoreError(
                "Paper-order exposure does not match "
                "quantity multiplied by limit price."
            )

        if status != "PAPER SUBMITTED":
            raise WebullPaperOrderStoreError(
                "Paper-order status must be PAPER SUBMITTED."
            )

        if not safety_reason:
            raise WebullPaperOrderStoreError(
                "safety_reason is required."
            )

        if lifecycle_status != "ENTRY PENDING":
            raise WebullPaperOrderStoreError(
                "New paper-order lifecycle status must be "
                "ENTRY PENDING."
            )

        if (
            (record.target_price is None)
            != (record.stop_price is None)
        ):
            raise WebullPaperOrderStoreError(
                "Paper-order target and stop must either "
                "both be present or both be absent."
            )

        target_price = None
        stop_price = None

        if record.target_price is not None:
            target_price = float(record.target_price)
            stop_price = float(record.stop_price)

            if target_price <= record.limit_price:
                raise WebullPaperOrderStoreError(
                    "Paper-order target must be above "
                    "the BUY limit price."
                )

            if stop_price <= 0:
                raise WebullPaperOrderStoreError(
                    "Paper-order stop must be positive."
                )

            if stop_price >= record.limit_price:
                raise WebullPaperOrderStoreError(
                    "Paper-order stop must be below "
                    "the BUY limit price."
                )


        WebullPaperOrderStore._format_datetime(
            record.created_at
        )
        WebullPaperOrderStore._format_datetime(
            record.submitted_at
        )

        if record.submitted_at < record.created_at:
            raise WebullPaperOrderStoreError(
                "submitted_at cannot precede created_at."
            )

        return WebullPaperOrderRecord(
            paper_order_id=paper_order_id,
            approval_reference=approval_reference,
            idempotency_key=idempotency_key,
            symbol=symbol,
            side=side,
            quantity=record.quantity,
            limit_price=round(record.limit_price, 4),
            proposed_exposure=expected_exposure,
            status=status,
            created_at=record.created_at.astimezone(UTC),
            submitted_at=record.submitted_at.astimezone(UTC),
            safety_reason=safety_reason,
            target_price=(
                None
                if target_price is None
                else round(target_price, 4)
            ),
            stop_price=(
                None
                if stop_price is None
                else round(stop_price, 4)
            ),
            lifecycle_status=lifecycle_status,
        )

    @staticmethod
    def _serialize_record(
        record: WebullPaperOrderRecord,
    ) -> dict[str, Any]:
        validated = (
            WebullPaperOrderStore._validate_record(
                record
            )
        )

        payload = asdict(validated)
        payload["created_at"] = (
            WebullPaperOrderStore._format_datetime(
                validated.created_at
            )
        )
        payload["submitted_at"] = (
            WebullPaperOrderStore._format_datetime(
                validated.submitted_at
            )
        )

        return payload

    @staticmethod
    def _parse_record(
        payload: Any,
    ) -> WebullPaperOrderRecord:
        if not isinstance(payload, dict):
            raise WebullPaperOrderStoreError(
                "Stored paper order must be an object."
            )

        required = {
            "paper_order_id",
            "approval_reference",
            "idempotency_key",
            "symbol",
            "side",
            "quantity",
            "limit_price",
            "proposed_exposure",
            "status",
            "created_at",
            "submitted_at",
            "safety_reason",
        }

        optional = {
            "target_price",
            "stop_price",
            "lifecycle_status",
        }

        unknown = set(payload) - required - optional
        missing = required - set(payload)

        if unknown:
            raise WebullPaperOrderStoreError(
                "Stored paper order contains unsupported "
                "fields: "
                + ", ".join(sorted(unknown))
            )

        if missing:
            raise WebullPaperOrderStoreError(
                "Stored paper order is missing fields: "
                + ", ".join(sorted(missing))
            )

        try:
            quantity = int(payload["quantity"])
            limit_price = float(payload["limit_price"])
            proposed_exposure = float(
                payload["proposed_exposure"]
            )
        except (TypeError, ValueError) as error:
            raise WebullPaperOrderStoreError(
                "Stored paper-order numeric fields "
                "are invalid."
            ) from error

        record = WebullPaperOrderRecord(
            paper_order_id=str(
                payload["paper_order_id"]
            ),
            approval_reference=str(
                payload["approval_reference"]
            ),
            idempotency_key=str(
                payload["idempotency_key"]
            ),
            symbol=str(payload["symbol"]),
            side=str(payload["side"]),
            quantity=quantity,
            limit_price=limit_price,
            proposed_exposure=proposed_exposure,
            status=str(payload["status"]),
            created_at=(
                WebullPaperOrderStore._parse_datetime(
                    payload["created_at"],
                    field_name="created_at",
                )
            ),
            submitted_at=(
                WebullPaperOrderStore._parse_datetime(
                    payload["submitted_at"],
                    field_name="submitted_at",
                )
            ),
            safety_reason=str(
                payload["safety_reason"]
            ),
            target_price=(
                None
                if payload.get("target_price") is None
                else float(payload["target_price"])
            ),
            stop_price=(
                None
                if payload.get("stop_price") is None
                else float(payload["stop_price"])
            ),
            lifecycle_status=str(
                payload.get(
                    "lifecycle_status",
                    "ENTRY PENDING",
                )
            ),
        )

        return WebullPaperOrderStore._validate_record(
            record
        )

    def load(
        self,
    ) -> dict[str, WebullPaperOrderRecord]:
        if not self.path.exists():
            return {}

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
            raise WebullPaperOrderStoreError(
                "Paper-order store could not be read."
            ) from error

        if not isinstance(payload, dict):
            raise WebullPaperOrderStoreError(
                "Paper-order store root must be an object."
            )

        if payload.get("version") != 1:
            raise WebullPaperOrderStoreError(
                "Unsupported paper-order store version."
            )

        raw_records = payload.get("records")

        if not isinstance(raw_records, list):
            raise WebullPaperOrderStoreError(
                "Paper-order records must be a list."
            )

        records: dict[str, WebullPaperOrderRecord] = {}
        idempotency_keys: set[str] = set()

        for raw_record in raw_records:
            record = self._parse_record(raw_record)

            if record.paper_order_id in records:
                raise WebullPaperOrderStoreError(
                    "Duplicate paper-order ID in store."
                )

            if record.idempotency_key in idempotency_keys:
                raise WebullPaperOrderStoreError(
                    "Duplicate idempotency key in store."
                )

            records[record.paper_order_id] = record
            idempotency_keys.add(
                record.idempotency_key
            )

        return records

    def save(
        self,
        records: dict[str, WebullPaperOrderRecord],
    ) -> None:
        validated: dict[str, WebullPaperOrderRecord] = {}
        idempotency_keys: set[str] = set()

        for key, raw_record in records.items():
            record = self._validate_record(raw_record)

            if key != record.paper_order_id:
                raise WebullPaperOrderStoreError(
                    "Paper-order dictionary key does not "
                    "match paper_order_id."
                )

            if record.idempotency_key in idempotency_keys:
                raise WebullPaperOrderStoreError(
                    "Duplicate idempotency key."
                )

            validated[key] = record
            idempotency_keys.add(
                record.idempotency_key
            )

        payload = {
            "version": 1,
            "records": [
                self._serialize_record(record)
                for record in sorted(
                    validated.values(),
                    key=lambda item: item.created_at,
                )
            ],
        }

        encoded = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n"

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            self.temp_path.write_text(
                encoded,
                encoding="utf-8",
            )
            os.chmod(self.temp_path, 0o600)
            os.replace(self.temp_path, self.path)
            os.chmod(self.path, 0o600)
        except OSError as error:
            try:
                self.temp_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise WebullPaperOrderStoreError(
                "Paper-order store could not be saved."
            ) from error

    def add(
        self,
        record: WebullPaperOrderRecord,
    ) -> None:
        validated = self._validate_record(record)
        records = self.load()

        if validated.paper_order_id in records:
            raise WebullPaperOrderStoreError(
                "DUPLICATE_PAPER_ORDER_ID"
            )

        if any(
            existing.idempotency_key
            == validated.idempotency_key
            for existing in records.values()
        ):
            raise WebullPaperOrderStoreError(
                "DUPLICATE_PAPER_SUBMISSION"
            )

        records[validated.paper_order_id] = validated
        self.save(records)
