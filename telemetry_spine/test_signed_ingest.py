import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest

from telemetry_spine.signed_ingest import (
    ReplayDetectedError,
    SignatureError,
    SignedTelemetryError,
    SignedTelemetryLedger,
    build_live_observation_packet,
    validate_payload,
    verify_signature,
)


def make_payload(**overrides):
    payload = {
        "schemaVersion": "eagle-eyes.signed-telemetry.v1",
        "sourceMode": "LIVE",
        "simulated": False,
        "sourceId": "sensor-alpha",
        "target": "TEST_CANARY_V1",
        "nonce": "0123456789abcdef",
        "sourceObservedAt": "2026-09-05T18:00:00Z",
        "position": {
            "latitude": 35.6895,
            "longitude": 139.6917,
            "altitudeM": 120.0,
        },
        "metadata": {"channel": "test"},
    }
    payload.update(overrides)
    return payload


def encoded(payload):
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def signature(secret, body, timestamp):
    message = str(timestamp).encode("ascii") + b"." + body
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


class SignedTelemetryValidationTests(unittest.TestCase):
    def test_valid_live_payload_is_accepted(self):
        payload = validate_payload(make_payload())
        self.assertEqual(payload["sourceMode"], "LIVE")
        self.assertIs(payload["simulated"], False)

    def test_live_payload_cannot_be_simulated(self):
        with self.assertRaises(SignedTelemetryError):
            validate_payload(make_payload(simulated=True))

    def test_invalid_coordinates_are_rejected(self):
        payload = make_payload()
        payload["position"] = {
            "latitude": 95.0,
            "longitude": 139.6917,
            "altitudeM": 10,
        }
        with self.assertRaises(SignedTelemetryError):
            validate_payload(payload)

    def test_signature_binds_timestamp_and_exact_body(self):
        secret = b"unit-test-secret"
        timestamp = 1_780_000_000
        body = encoded(make_payload())
        sig = signature(secret, body, timestamp)
        digest = verify_signature(
            secret,
            body,
            sig,
            str(timestamp),
            now=timestamp,
        )
        self.assertEqual(digest, hashlib.sha256(body).hexdigest())

        tampered = body.replace(b"TEST_CANARY_V1", b"TEST_CANARY_V2")
        with self.assertRaises(SignatureError):
            verify_signature(
                secret,
                tampered,
                sig,
                str(timestamp),
                now=timestamp,
            )

    def test_stale_signature_is_rejected(self):
        secret = b"unit-test-secret"
        timestamp = 1_780_000_000
        body = encoded(make_payload())
        sig = signature(secret, body, timestamp)
        with self.assertRaises(SignatureError):
            verify_signature(
                secret,
                body,
                sig,
                str(timestamp),
                now=timestamp + 61,
                max_clock_skew_s=60,
            )


class SignedTelemetryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "ledger.db")
        self.ledger = SignedTelemetryLedger(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_ledger_uses_wal_and_rejects_replayed_nonce(self):
        payload = make_payload()
        body = encoded(payload)
        digest = hashlib.sha256(body).hexdigest()
        receipt = self.ledger.append(
            payload,
            payload_sha256=digest,
            signature="a" * 64,
            received_at_ms=123456789,
        )
        self.assertEqual(receipt.ledger_id, 1)

        with sqlite3.connect(self.db_path) as connection:
            mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

        with self.assertRaises(ReplayDetectedError):
            self.ledger.append(
                payload,
                payload_sha256=digest,
                signature="a" * 64,
                received_at_ms=123456790,
            )

    def test_test_and_replay_modes_are_ledgerable_but_not_live_publishable(self):
        for index, mode in enumerate(("TEST", "REPLAY"), start=1):
            payload = make_payload(
                sourceMode=mode,
                simulated=True,
                nonce=f"0123456789abcde{index}",
            )
            body = encoded(payload)
            receipt = self.ledger.append(
                payload,
                payload_sha256=hashlib.sha256(body).hexdigest(),
                signature="b" * 64,
            )
            with self.assertRaises(SignedTelemetryError):
                build_live_observation_packet(payload, receipt)

    def test_live_packet_is_explicitly_observation_only(self):
        payload = make_payload()
        body = encoded(payload)
        receipt = self.ledger.append(
            payload,
            payload_sha256=hashlib.sha256(body).hexdigest(),
            signature="c" * 64,
        )
        outbound = build_live_observation_packet(payload, receipt)
        self.assertEqual(outbound["source_mode"], "LIVE")
        self.assertIs(outbound["simulated"], False)
        self.assertEqual(outbound["authority"]["type"], "observation")
        self.assertIs(outbound["authority"]["commandEligible"], False)
        self.assertIs(outbound["integrity"]["hmac_verified"], True)
        self.assertIs(outbound["integrity"]["replay_protected"], True)


if __name__ == "__main__":
    unittest.main()
