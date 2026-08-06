import json
import os
from datetime import UTC, datetime

import pytest

from trading_bot.webull_preview_store import (
    WebullPreviewStore,
    WebullPreviewStoreError,
)


def preview():
    return {
        "symbol": "OPEN",
        "quantity": 10,
        "limitPrice": 4.25,
        "proposedExposure": 42.5,
        "status": "PREVIEW READY",
        "createdAt": datetime(
            2026,
            8,
            6,
            18,
            30,
            tzinfo=UTC,
        ).isoformat(),
    }


def test_preview_survives_restart(tmp_path):
    path = tmp_path / "previews.json"

    WebullPreviewStore(path).save_previews([
        preview()
    ])

    restarted = WebullPreviewStore(path)

    stored = restarted.load_preview("open")

    assert stored is not None
    assert stored["symbol"] == "OPEN"
    assert stored["quantity"] == 10
    assert stored["limitPrice"] == 4.25
    assert stored["proposedExposure"] == 42.5


def test_store_file_is_private(tmp_path):
    path = tmp_path / "previews.json"

    WebullPreviewStore(path).save_previews([
        preview()
    ])

    assert os.stat(path).st_mode & 0o777 == 0o600


def test_rejects_sensitive_fields(tmp_path):
    unsafe = preview()
    unsafe["approvalToken"] = "secret"

    with pytest.raises(
        WebullPreviewStoreError,
        match="unsupported fields",
    ):
        WebullPreviewStore(
            tmp_path / "previews.json"
        ).save_previews([unsafe])


def test_rejects_exposure_mismatch(tmp_path):
    invalid = preview()
    invalid["proposedExposure"] = 99.0

    with pytest.raises(
        WebullPreviewStoreError,
        match="does not match",
    ):
        WebullPreviewStore(
            tmp_path / "previews.json"
        ).save_previews([invalid])


def test_file_contains_only_redacted_fields(
    tmp_path,
):
    path = tmp_path / "previews.json"

    WebullPreviewStore(path).save_previews([
        preview()
    ])

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )
    record = payload["previews"][0]

    assert set(record) == {
        "symbol",
        "quantity",
        "limitPrice",
        "proposedExposure",
        "status",
        "createdAt",
    }

    serialized = json.dumps(payload)

    assert "approvalToken" not in serialized
    assert "accountId" not in serialized
    assert "token_hash" not in serialized
    assert "proposalFingerprint" not in serialized
