import hashlib
import hmac
import json
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SCHEMA_VERSION = "eagle-eyes.signed-telemetry.v1"
ALLOWED_SOURCE_MODES = frozenset({"LIVE", "TEST", "REPLAY"})


class SignedTelemetryError(ValueError):
    """Base error for signed telemetry validation failures."""


class SignatureError(SignedTelemetryError):
    """Raised when request authentication or freshness validation fails."""


class ReplayDetectedError(SignedTelemetryError):
    """Raised when a source reuses an already accepted nonce."""


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _bounded_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise SignedTelemetryError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise SignedTelemetryError(
            f"{field} is required and must be at most {maximum} characters"
        )
    return normalized


def _validate_iso8601(value: Any, field: str) -> str:
    text = _bounded_text(value, field, 64)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise SignedTelemetryError(f"{field} must be ISO-8601") from exc
    return text


def validate_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise SignedTelemetryError("payload must be a JSON object")

    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise SignedTelemetryError(f"schemaVersion must be {SCHEMA_VERSION}")

    source_mode = payload.get("sourceMode")
    if source_mode not in ALLOWED_SOURCE_MODES:
        raise SignedTelemetryError(
            "sourceMode must be one of LIVE, TEST, or REPLAY"
        )

    source_id = _bounded_text(payload.get("sourceId"), "sourceId", 64)
    target = _bounded_text(payload.get("target"), "target", 128)
    nonce = _bounded_text(payload.get("nonce"), "nonce", 128)
    if len(nonce) < 16:
        raise SignedTelemetryError("nonce must be at least 16 characters")

    source_observed_at = _validate_iso8601(
        payload.get("sourceObservedAt"), "sourceObservedAt"
    )

    simulated = payload.get("simulated")
    if not isinstance(simulated, bool):
        raise SignedTelemetryError("simulated must be a boolean")
    if source_mode == "LIVE" and simulated is not False:
        raise SignedTelemetryError(
            "LIVE telemetry must explicitly declare simulated=false"
        )

    position = payload.get("position")
    if not isinstance(position, dict):
        raise SignedTelemetryError("position must be an object")

    latitude = position.get("latitude")
    longitude = position.get("longitude")
    altitude_m = position.get("altitudeM")

    if not _finite_number(latitude) or not -90 <= float(latitude) <= 90:
        raise SignedTelemetryError("position.latitude must be a valid latitude")
    if not _finite_number(longitude) or not -180 <= float(longitude) <= 180:
        raise SignedTelemetryError("position.longitude must be a valid longitude")
    if altitude_m is not None and not _finite_number(altitude_m):
        raise SignedTelemetryError(
            "position.altitudeM must be finite when supplied"
        )

    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise SignedTelemetryError("metadata must be an object when supplied")

    normalized = dict(payload)
    normalized["sourceId"] = source_id
    normalized["target"] = target
    normalized["nonce"] = nonce
    normalized["sourceObservedAt"] = source_observed_at
    normalized["position"] = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "altitudeM": float(altitude_m) if altitude_m is not None else None,
    }
    return normalized


def verify_signature(
    secret: bytes,
    raw_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    *,
    now: int | None = None,
    max_clock_skew_s: int = 60,
) -> str:
    if not secret:
        raise SignatureError("signed telemetry HMAC secret is not configured")
    if not raw_body:
        raise SignatureError("request body is empty")
    if not signature_header:
        raise SignatureError("missing X-Eagle-Eyes-Signature header")
    if not timestamp_header:
        raise SignatureError("missing X-Eagle-Eyes-Timestamp header")

    try:
        request_timestamp = int(timestamp_header)
    except (TypeError, ValueError) as exc:
        raise SignatureError("X-Eagle-Eyes-Timestamp must be Unix seconds") from exc

    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - request_timestamp) > max_clock_skew_s:
        raise SignatureError("signed telemetry request timestamp is outside allowed skew")

    supplied = signature_header.strip().lower()
    if supplied.startswith("sha256="):
        supplied = supplied[7:]
    if len(supplied) != 64:
        raise SignatureError("X-Eagle-Eyes-Signature must be a SHA-256 HMAC hex digest")
    try:
        bytes.fromhex(supplied)
    except ValueError as exc:
        raise SignatureError("X-Eagle-Eyes-Signature is not valid hexadecimal") from exc

    signed_message = str(request_timestamp).encode("ascii") + b"." + raw_body
    computed = hmac.new(secret, signed_message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, supplied):
        raise SignatureError("signed telemetry HMAC validation failed")

    return hashlib.sha256(raw_body).hexdigest()


@dataclass(frozen=True)
class LedgerReceipt:
    ledger_id: int
    payload_sha256: str
    source_mode: str
    source_id: str
    nonce: str
    received_at_ms: int


class SignedTelemetryLedger:
    def __init__(self, db_path: str):
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("db_path is required")
        self.db_path = db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signed_telemetry_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at_ms INTEGER NOT NULL,
                    source_observed_at TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target TEXT NOT NULL,
                    source_mode TEXT NOT NULL CHECK(source_mode IN ('LIVE','TEST','REPLAY')),
                    simulated INTEGER NOT NULL CHECK(simulated IN (0,1)),
                    nonce TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    altitude_m REAL,
                    payload_sha256 TEXT NOT NULL,
                    signature_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(source_id, nonce)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_signed_telemetry_received_at "
                "ON signed_telemetry_ledger(received_at_ms)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_signed_telemetry_source_mode "
                "ON signed_telemetry_ledger(source_mode)"
            )

    def append(
        self,
        payload: dict,
        *,
        payload_sha256: str,
        signature: str,
        received_at_ms: int | None = None,
    ) -> LedgerReceipt:
        normalized = validate_payload(payload)
        received = int(time.time() * 1000) if received_at_ms is None else int(received_at_ms)
        position = normalized["position"]
        canonical_payload = json.dumps(
            normalized,
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        )

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO signed_telemetry_ledger (
                        received_at_ms,
                        source_observed_at,
                        source_id,
                        target,
                        source_mode,
                        simulated,
                        nonce,
                        latitude,
                        longitude,
                        altitude_m,
                        payload_sha256,
                        signature_sha256,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        received,
                        normalized["sourceObservedAt"],
                        normalized["sourceId"],
                        normalized["target"],
                        normalized["sourceMode"],
                        1 if normalized["simulated"] else 0,
                        normalized["nonce"],
                        position["latitude"],
                        position["longitude"],
                        position["altitudeM"],
                        payload_sha256,
                        signature,
                        canonical_payload,
                    ),
                )
                ledger_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ReplayDetectedError(
                    "signed telemetry nonce has already been accepted for this source"
                ) from exc
            raise

        return LedgerReceipt(
            ledger_id=ledger_id,
            payload_sha256=payload_sha256,
            source_mode=normalized["sourceMode"],
            source_id=normalized["sourceId"],
            nonce=normalized["nonce"],
            received_at_ms=received,
        )

    def stats(self) -> dict:
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM signed_telemetry_ledger"
            ).fetchone()[0]
            live = connection.execute(
                "SELECT COUNT(*) FROM signed_telemetry_ledger WHERE source_mode='LIVE'"
            ).fetchone()[0]
        return {"total": int(total), "live": int(live)}


def build_live_observation_packet(payload: dict, receipt: LedgerReceipt) -> dict:
    normalized = validate_payload(payload)
    if normalized["sourceMode"] != "LIVE" or normalized["simulated"] is not False:
        raise SignedTelemetryError(
            "only LIVE non-simulated telemetry can be published to the live observation stream"
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "source_type": "signed-telemetry",
        "source_mode": "LIVE",
        "simulated": False,
        "source_id": normalized["sourceId"],
        "target": normalized["target"],
        "source_observed_at": normalized["sourceObservedAt"],
        "received_at_ms": receipt.received_at_ms,
        "position": normalized["position"],
        "metadata": normalized.get("metadata") or {},
        "integrity": {
            "ledger_id": receipt.ledger_id,
            "payload_sha256": receipt.payload_sha256,
            "hmac_verified": True,
            "replay_protected": True,
        },
        "authority": {
            "type": "observation",
            "commandEligible": False,
        },
    }
