"""joflux package metadata."""

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    """Return the installed package version, or a development fallback."""
    try:
        return version("joflux")
    except PackageNotFoundError:
        return "0.1.0-dev"


__all__ = ["package_version"]
