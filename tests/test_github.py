"""GitHub client tests."""

import pytest

from joflux.github import web_location


@pytest.mark.parametrize(
    ("api_url", "expected"),
    [
        ("https://api.github.com", "github.com/acme"),
        ("https://api.github.com/", "github.com/acme"),
        ("https://ghe.example.com/api/v3", "ghe.example.com/acme"),
        ("https://ghe.example.com/api/v3/", "ghe.example.com/acme"),
        ("https://ghe.example.com:8443/api/v3", "ghe.example.com:8443/acme"),
        ("https://api.octo.ghe.com", "octo.ghe.com/acme"),
    ],
)
def test_web_location_follows_the_configured_api(api_url: str, expected: str) -> None:
    """The organization's address comes from the API URL, not a hard-coded github.com."""
    assert web_location(api_url, "acme") == expected
