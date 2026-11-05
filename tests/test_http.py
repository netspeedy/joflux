"""HTTP helper tests."""

import http.client as http_client
import io
import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from joflux import http
from joflux.http import APIError, NoAnswerError, request_json

URL = "https://forge.example/api/v1/repos/target/example"


def _fake_urlopen(monkeypatch, outcome: BaseException) -> None:
    def fake_urlopen(_request: Any, timeout: int = 30) -> Any:
        del timeout
        raise outcome

    monkeypatch.setattr(http, "urlopen", fake_urlopen)


def _http_error(code: int) -> HTTPError:
    return HTTPError(URL, code, "error", None, io.BytesIO(json.dumps({"message": "x"}).encode()))


@pytest.mark.parametrize(
    "outcome",
    [
        TimeoutError("timed out"),
        ConnectionResetError("Remote end closed connection without response"),
    ],
)
def test_a_request_with_no_answer_raises_no_answer_error(monkeypatch, outcome) -> None:
    """A timeout or dropped connection after the request went out is a handled API error."""
    _fake_urlopen(monkeypatch, outcome)

    with pytest.raises(NoAnswerError) as exc_info:
        request_json("GET", URL, {})

    assert exc_info.value.status is None
    assert str(exc_info.value) == f"no answer from {URL}: {outcome}"


@pytest.mark.parametrize("code", [504, 524])
def test_a_gateway_timeout_raises_no_answer_error(monkeypatch, code: int) -> None:
    """A gateway that gave up on the server behind it isn't the server's answer."""
    _fake_urlopen(monkeypatch, _http_error(code))

    with pytest.raises(NoAnswerError) as exc_info:
        request_json("POST", URL, {}, payload={})

    assert exc_info.value.status == code


@pytest.mark.parametrize(
    "outcome",
    [
        _http_error(500),
        _http_error(409),
        URLError(TimeoutError("timed out")),
        URLError(ConnectionRefusedError("refused")),
    ],
)
def test_answers_and_unsent_requests_stay_plain_api_errors(monkeypatch, outcome) -> None:
    """An error answer, or a request that never reached the server, isn't a missing answer."""
    _fake_urlopen(monkeypatch, outcome)

    with pytest.raises(APIError) as exc_info:
        request_json("GET", URL, {})

    assert not isinstance(exc_info.value, NoAnswerError)


def test_allowed_statuses_come_back_before_gateway_handling(monkeypatch) -> None:
    """A caller that allows a status gets it back, even a gateway timeout."""
    _fake_urlopen(monkeypatch, _http_error(504))

    assert request_json("GET", URL, {}, allow_status=(504,))["_status"] == 504


class _CutOffResponse:
    """A response whose body stops short of its Content-Length."""

    def __enter__(self) -> "_CutOffResponse":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        """Fail the way http.client does when the connection ends early."""
        raise http_client.IncompleteRead(b'{"id": 7', 20)


def test_an_answer_cut_off_partway_raises_no_answer_error(monkeypatch) -> None:
    """IncompleteRead isn't an OSError, so without this it ended the run with a traceback."""
    monkeypatch.setattr(http, "urlopen", lambda _request, timeout=30: _CutOffResponse())

    with pytest.raises(NoAnswerError) as exc_info:
        request_json("POST", URL, {}, payload={})

    assert str(exc_info.value).startswith(f"incomplete answer from {URL}: IncompleteRead(")


def test_a_tls_error_while_reading_raises_no_answer_error(monkeypatch) -> None:
    """After the handshake, a TLS error means the answer was lost on the way."""
    error = ssl.SSLError(1, "[SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC] decryption failed")
    _fake_urlopen(monkeypatch, error)

    with pytest.raises(NoAnswerError) as exc_info:
        request_json("GET", URL, {})

    assert exc_info.value.status is None


def test_a_tls_handshake_error_stays_a_plain_api_error(monkeypatch) -> None:
    """urlopen wraps a handshake failure in URLError: the request never reached the server."""
    handshake = ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED]")
    _fake_urlopen(monkeypatch, URLError(handshake))

    with pytest.raises(APIError) as exc_info:
        request_json("GET", URL, {})

    assert not isinstance(exc_info.value, NoAnswerError)
    assert str(exc_info.value).startswith(f"failed to connect to {URL}:")


class _CutOffBody:
    """An error answer's body that stops short."""

    def read(self, *_args) -> bytes:
        """Fail partway through, keeping what arrived."""
        raise http_client.IncompleteRead(b'{"message": "boo', 30)

    def close(self) -> None:
        """Nothing to release."""


def test_an_error_answer_with_a_cut_off_body_keeps_its_status(monkeypatch) -> None:
    """The status line arrived intact, so the error is still that answer, with what body came."""
    _fake_urlopen(monkeypatch, HTTPError(URL, 500, "error", None, _CutOffBody()))

    with pytest.raises(APIError) as exc_info:
        request_json("GET", URL, {})

    assert not isinstance(exc_info.value, NoAnswerError)
    assert exc_info.value.status == 500
    assert exc_info.value.body == '{"message": "boo'
