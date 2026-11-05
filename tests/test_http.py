"""HTTP helper tests."""

import io
import json
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
