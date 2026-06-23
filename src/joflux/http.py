"""HTTP helpers for JSON APIs."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class APIError(RuntimeError):
    """Raised when an API request fails."""

    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


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
        response_body = exc.read().decode("utf-8", errors="replace")
        if exc.code in allow_status:
            return {"_status": exc.code, "_body": response_body}
        raise APIError(f"HTTP {exc.code} from {request_url}", exc.code, response_body) from exc
    except URLError as exc:
        raise APIError(f"failed to connect to {request_url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise APIError(f"invalid JSON response from {request_url}: {exc}") from exc
