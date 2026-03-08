"""Tests for src/gamechanger/signing.py -- gc-signature HMAC-SHA256 signing module.  # synthetic-test-data"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from unittest.mock import patch

import pytest

from src.gamechanger.signing import (
    build_signature_headers,
    sign_payload,
    values_for_signer,
)


# ---------------------------------------------------------------------------
# AC-2: Body value extraction
# ---------------------------------------------------------------------------


class TestValuesForSigner:
    """AC-2: values_for_signer handles all JSON-equivalent cases."""

    def test_string_returns_as_is(self) -> None:
        assert values_for_signer("hello") == ["hello"]

    def test_empty_string_returns_as_is(self) -> None:
        assert values_for_signer("") == [""]

    def test_integer_returns_string_representation(self) -> None:
        assert values_for_signer(42) == ["42"]

    def test_float_whole_number_returns_int_string(self) -> None:
        # JS Number -> String("3.0") = "3", not "3.0"
        assert values_for_signer(3.0) == ["3"]

    def test_float_fractional_returns_string(self) -> None:
        assert values_for_signer(3.14) == ["3.14"]

    def test_none_returns_null_string(self) -> None:
        assert values_for_signer(None) == ["null"]

    def test_list_flatmaps_elements(self) -> None:
        assert values_for_signer([1, 2, 3]) == ["1", "2", "3"]

    def test_empty_list_returns_empty(self) -> None:
        assert values_for_signer([]) == []

    def test_list_of_strings(self) -> None:
        assert values_for_signer(["a", "b"]) == ["a", "b"]

    def test_simple_dict_extracts_value(self) -> None:
        # {"type": "refresh"} -> ["refresh"]
        assert values_for_signer({"type": "refresh"}) == ["refresh"]

    def test_dict_keys_sorted_alphabetically(self) -> None:
        # {"type": "client-auth", "client_id": "abc"}
        # sorted keys: client_id, type -> ["abc", "client-auth"]
        result = values_for_signer({"type": "client-auth", "client_id": "abc"})
        assert result == ["abc", "client-auth"]

    def test_nested_dict_recursively_extracted(self) -> None:
        # {"a": {"z": "last", "a": "first"}} -> sorted inner keys: a, z -> ["first", "last"]
        result = values_for_signer({"a": {"z": "last", "a": "first"}})
        assert result == ["first", "last"]

    def test_dict_with_none_value(self) -> None:
        assert values_for_signer({"key": None}) == ["null"]

    def test_list_nested_in_dict(self) -> None:
        result = values_for_signer({"items": ["x", "y"]})
        assert result == ["x", "y"]

    def test_empty_dict_returns_empty(self) -> None:
        # Empty dict: no keys to sort, no values to extract
        assert values_for_signer({}) == []

    def test_list_containing_dicts(self) -> None:
        result = values_for_signer([{"b": "2", "a": "1"}])
        assert result == ["1", "2"]

    def test_real_refresh_body(self) -> None:
        # The actual POST /auth body for token refresh
        assert values_for_signer({"type": "refresh"}) == ["refresh"]


# ---------------------------------------------------------------------------
# AC-3: HMAC signing with known input/output pair
# ---------------------------------------------------------------------------


class TestSignPayload:
    """AC-3: sign_payload produces correct HMAC-SHA256 with known inputs."""

    def _make_key(self, secret: bytes) -> str:
        """Helper: Base64-encode raw key bytes."""
        return base64.b64encode(secret).decode()

    def _make_nonce(self, nonce_bytes: bytes) -> str:
        """Helper: Base64-encode raw nonce bytes."""
        return base64.b64encode(nonce_bytes).decode()

    def test_known_input_output_pair(self) -> None:
        """Verify HMAC output against a reference computed independently."""
        secret = b"A" * 32
        nonce = b"N" * 32
        timestamp = 1700000000
        body = {"type": "refresh"}

        client_key_b64 = self._make_key(secret)
        nonce_b64 = self._make_nonce(nonce)

        body_values = ["refresh"]  # values_for_signer({"type": "refresh"})

        # Reconstruct expected HMAC independently
        mac = hmac.new(secret, digestmod=hashlib.sha256)
        mac.update((str(timestamp) + "|").encode())
        mac.update(nonce)
        mac.update(b"|")
        mac.update("|".join(body_values).encode())
        expected = base64.b64encode(mac.digest()).decode()

        result = sign_payload(
            client_key_b64=client_key_b64,
            timestamp=timestamp,
            nonce_b64=nonce_b64,
            body=body,
        )
        assert result == expected

    def test_with_previous_signature(self) -> None:
        """Verify HMAC includes previous signature bytes when provided."""
        secret = b"K" * 32
        nonce = b"N" * 32
        prev_sig = b"S" * 32
        timestamp = 1700000001
        body = {"type": "user-auth", "email": "user@example.com"}

        client_key_b64 = self._make_key(secret)
        nonce_b64 = self._make_nonce(nonce)
        prev_sig_b64 = self._make_nonce(prev_sig)

        body_values = values_for_signer(body)

        mac = hmac.new(secret, digestmod=hashlib.sha256)
        mac.update((str(timestamp) + "|").encode())
        mac.update(nonce)
        mac.update(b"|")
        mac.update("|".join(body_values).encode())
        mac.update(b"|")
        mac.update(prev_sig)
        expected = base64.b64encode(mac.digest()).decode()

        result = sign_payload(
            client_key_b64=client_key_b64,
            timestamp=timestamp,
            nonce_b64=nonce_b64,
            body=body,
            previous_signature_b64=prev_sig_b64,
        )
        assert result == expected

    def test_without_previous_signature_differs_from_with(self) -> None:
        """Omitting previousSignature produces a different HMAC than including it."""
        secret = b"K" * 32
        nonce = b"N" * 32
        prev_sig = b"S" * 32
        timestamp = 1700000002
        body = {"type": "refresh"}

        client_key_b64 = self._make_key(secret)
        nonce_b64 = self._make_nonce(nonce)
        prev_sig_b64 = self._make_nonce(prev_sig)

        without = sign_payload(client_key_b64, timestamp, nonce_b64, body)
        with_prev = sign_payload(client_key_b64, timestamp, nonce_b64, body, prev_sig_b64)
        assert without != with_prev

    def test_sorted_body_keys_affect_hmac(self) -> None:
        """Different key ordering in input must NOT change HMAC (sorting is applied)."""
        secret = b"K" * 32
        nonce = b"N" * 32
        timestamp = 1700000003

        client_key_b64 = self._make_key(secret)
        nonce_b64 = self._make_nonce(nonce)

        # Python 3.7+ dicts preserve insertion order; test that both orderings give same result
        body_a = {"type": "client-auth", "client_id": "abc"}
        body_b = {"client_id": "abc", "type": "client-auth"}

        result_a = sign_payload(client_key_b64, timestamp, nonce_b64, body_a)
        result_b = sign_payload(client_key_b64, timestamp, nonce_b64, body_b)
        assert result_a == result_b

    def test_nonce_used_as_raw_bytes_not_string(self) -> None:
        """Confirm nonce is decoded to bytes; using raw Base64 string would differ."""
        secret = b"K" * 32
        nonce_bytes = b"N" * 32
        timestamp = 1700000004
        body = {"type": "refresh"}

        client_key_b64 = base64.b64encode(secret).decode()
        nonce_b64 = base64.b64encode(nonce_bytes).decode()

        # Compute what it would be if nonce were used as a string (incorrect)
        mac_wrong = hmac.new(secret, digestmod=hashlib.sha256)
        mac_wrong.update((str(timestamp) + "|").encode())
        mac_wrong.update(nonce_b64.encode())  # string, not bytes
        mac_wrong.update(b"|")
        mac_wrong.update("refresh".encode())
        wrong = base64.b64encode(mac_wrong.digest()).decode()

        correct = sign_payload(client_key_b64, timestamp, nonce_b64, body)
        # Must NOT equal the incorrect string-based computation
        assert correct != wrong


# ---------------------------------------------------------------------------
# AC-4: Header assembly
# ---------------------------------------------------------------------------


class TestBuildSignatureHeaders:
    """AC-4: build_signature_headers generates correct header structure."""

    def test_returns_three_required_keys(self) -> None:
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        headers = build_signature_headers(
            client_id="test-client-id",
            client_key_b64=client_key_b64,
            body={"type": "refresh"},
        )
        assert set(headers.keys()) == {"gc-signature", "gc-timestamp", "gc-client-id"}

    def test_gc_client_id_matches_input(self) -> None:
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        headers = build_signature_headers(
            client_id="my-client-uuid",
            client_key_b64=client_key_b64,
            body={"type": "refresh"},
        )
        assert headers["gc-client-id"] == "my-client-uuid"

    def test_gc_timestamp_is_string_of_unix_seconds(self) -> None:
        frozen_time = 1700000000
        client_key_b64 = base64.b64encode(b"K" * 32).decode()

        with patch("src.gamechanger.signing.time.time", return_value=float(frozen_time)):
            headers = build_signature_headers(
                client_id="cid",
                client_key_b64=client_key_b64,
                body={"type": "refresh"},
            )

        assert headers["gc-timestamp"] == str(frozen_time)

    def test_gc_signature_format_nonce_dot_hmac(self) -> None:
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        headers = build_signature_headers(
            client_id="cid",
            client_key_b64=client_key_b64,
            body={"type": "refresh"},
        )
        parts = headers["gc-signature"].split(".")
        assert len(parts) == 2, "gc-signature must be nonce.hmac"
        nonce_b64, hmac_b64 = parts
        # Both parts should be valid Base64
        assert base64.b64decode(nonce_b64)
        assert base64.b64decode(hmac_b64)

    def test_nonce_is_32_bytes(self) -> None:
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        headers = build_signature_headers(
            client_id="cid",
            client_key_b64=client_key_b64,
            body={"type": "refresh"},
        )
        nonce_b64 = headers["gc-signature"].split(".")[0]
        assert len(base64.b64decode(nonce_b64)) == 32

    def test_nonce_is_random_each_call(self) -> None:
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        headers_1 = build_signature_headers("cid", client_key_b64, {"type": "refresh"})
        headers_2 = build_signature_headers("cid", client_key_b64, {"type": "refresh"})
        nonce_1 = headers_1["gc-signature"].split(".")[0]
        nonce_2 = headers_2["gc-signature"].split(".")[0]
        # Statistically impossible to collide with 32 random bytes
        assert nonce_1 != nonce_2

    def test_hmac_reproducible_with_fixed_nonce_and_timestamp(self) -> None:
        """With frozen time and fixed nonce, the HMAC output is deterministic."""
        frozen_time = 1700000000
        fixed_nonce = b"F" * 32
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        body = {"type": "refresh"}

        with (
            patch("src.gamechanger.signing.time.time", return_value=float(frozen_time)),
            patch("src.gamechanger.signing.os.urandom", return_value=fixed_nonce),
        ):
            h1 = build_signature_headers("cid", client_key_b64, body)
            h2 = build_signature_headers("cid", client_key_b64, body)

        assert h1["gc-signature"] == h2["gc-signature"]

    def test_hmac_matches_sign_payload(self) -> None:
        """The HMAC part of gc-signature matches what sign_payload computes."""
        frozen_time = 1700000005
        fixed_nonce = b"X" * 32
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        body = {"type": "refresh"}

        with (
            patch("src.gamechanger.signing.time.time", return_value=float(frozen_time)),
            patch("src.gamechanger.signing.os.urandom", return_value=fixed_nonce),
        ):
            headers = build_signature_headers("cid", client_key_b64, body)

        nonce_b64, hmac_in_header = headers["gc-signature"].split(".")
        expected_hmac = sign_payload(
            client_key_b64=client_key_b64,
            timestamp=frozen_time,
            nonce_b64=nonce_b64,
            body=body,
        )
        assert hmac_in_header == expected_hmac

    def test_accepts_previous_signature(self) -> None:
        """build_signature_headers passes previous_signature_b64 through to sign_payload."""
        frozen_time = 1700000006
        fixed_nonce = b"Y" * 32
        client_key_b64 = base64.b64encode(b"K" * 32).decode()
        prev_sig_b64 = base64.b64encode(b"P" * 32).decode()
        body = {"type": "user-auth", "email": "test@example.com"}

        with (
            patch("src.gamechanger.signing.time.time", return_value=float(frozen_time)),
            patch("src.gamechanger.signing.os.urandom", return_value=fixed_nonce),
        ):
            headers_with = build_signature_headers("cid", client_key_b64, body, prev_sig_b64)
            headers_without = build_signature_headers("cid", client_key_b64, body)

        # Including previous_signature must change the HMAC
        sig_with = headers_with["gc-signature"].split(".")[1]
        sig_without = headers_without["gc-signature"].split(".")[1]
        assert sig_with != sig_without


# ---------------------------------------------------------------------------
# AC-5: No credential logging
# ---------------------------------------------------------------------------


class TestNoCredentialLogging:
    """AC-5: Signing functions do not log credentials at any log level."""

    def test_sign_payload_does_not_log_key(self, caplog: pytest.LogCaptureFixture) -> None:
        secret = b"SECRET_KEY_BYTES_32B"
        client_key_b64 = base64.b64encode(secret).decode()
        nonce_b64 = base64.b64encode(b"N" * 32).decode()

        with caplog.at_level("DEBUG", logger="src.gamechanger.signing"):
            sign_payload(client_key_b64, 1700000000, nonce_b64, {"type": "refresh"})

        for record in caplog.records:
            assert client_key_b64 not in record.getMessage(), (
                f"client_key_b64 found in log: {record.getMessage()}"
            )

    def test_build_signature_headers_does_not_log_key(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        secret = b"ANOTHER_SECRET_32BYT"
        client_key_b64 = base64.b64encode(secret).decode()

        with caplog.at_level("DEBUG", logger="src.gamechanger.signing"):
            build_signature_headers("cid", client_key_b64, {"type": "refresh"})

        for record in caplog.records:
            assert client_key_b64 not in record.getMessage(), (
                f"client_key_b64 found in log: {record.getMessage()}"
            )

    def test_build_signature_headers_does_not_log_signature(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client_key_b64 = base64.b64encode(b"K" * 32).decode()

        with caplog.at_level("DEBUG", logger="src.gamechanger.signing"):
            headers = build_signature_headers("cid", client_key_b64, {"type": "refresh"})

        gc_sig = headers["gc-signature"]
        for record in caplog.records:
            assert gc_sig not in record.getMessage(), (
                f"gc-signature value found in log: {record.getMessage()}"
            )
