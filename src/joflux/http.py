"""HTTP helpers for JSON APIs."""

from __future__ import annotations

import json
import ssl
from http.client import IncompleteRead
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Gateways answer 504, or 524 behind Cloudflare, when the server behind them didn't answer in time.
GATEWAY_TIMEOUT_STATUSES = (504, 524)


class APIError(RuntimeError):
    """Raised when an API request fails."""

    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


class NoAnswerError(APIError):
    """Raised when a request went out but no intact answer came back.

    That covers a response that timed out, a connection that dropped before the answer arrived,
    an answer cut off partway or broken by a TLS error while it was being read, and a gateway that
    gave up waiting on the server behind it. The server may still act on the request, or may
    already have. A connection that never opened is a plain APIError, because the request never
    reached the server.
    """


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    allow_status: tuple[int, ...] = (),
) -> Any:
    """Run a JSON HTTP request and return decoded JSON data."""
    request_url = url
    if params:
        request_url = f"{url}?{urlencode(params)}"

    body: bytes | None = None
    request_headers = dict(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(request_url, data=body, headers=request_headers, method=method)

    try:
        with urlopen(
            request, timeout=timeout
        ) as response:  # noqa: S310 - user-supplied API URLs are intentional.
            response_body = response.read().decode("utf-8")
            if not response_body:
                return None
            return json.loads(response_body)
    except HTTPError as exc:
        response_body = _error_body(exc)
        if exc.code in allow_status:
            return {"_status": exc.code, "_body": response_body}
        error = NoAnswerError if exc.code in GATEWAY_TIMEOUT_STATUSES else APIError
        raise error(f"HTTP {exc.code} from {request_url}", exc.code, response_body) from exc
    except URLError as exc:
        # urlopen wraps anything raised while sending the request, connecting included, in
        # URLError, so the server never saw it.
        raise APIError(f"failed to connect to {request_url}: {exc.reason}") from exc
    except (TimeoutError, ConnectionError) as exc:
        # These come from waiting for or reading the response, after the request went out.
        raise NoAnswerError(f"no answer from {request_url}: {exc}") from exc
    except (IncompleteRead, ssl.SSLError) as exc:
        # The answer started to arrive but not intact. A TLS handshake error can't land here: the
        # handshake runs while the request is sent, so urlopen wraps it in URLError above.
        raise NoAnswerError(f"incomplete answer from {request_url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise APIError(f"invalid JSON response from {request_url}: {exc}") from exc


def _error_body(exc: HTTPError) -> str:
    """Return an error answer's body, or as much of it as arrived.

    The status line already came through intact, so a body that's cut off or lost doesn't change
    what the answer was.
    """
    try:
        raw = exc.read()
    except IncompleteRead as cut:
        raw = cut.partial
    except (TimeoutError, ConnectionError, ssl.SSLError):
        raw = b""
    return raw.decode("utf-8", errors="replace")
