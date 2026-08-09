"""Browser cookie import — the key to strong Facebook & Instagram support.

Facebook and Instagram serve almost nothing to anonymous clients. yt-dlp can read
the cookies straight out of an installed browser profile
(``--cookies-from-browser``), which makes logged-in pages downloadable without
ever typing a password into this app.

Two sources are supported:

* **Browser** – yt-dlp decrypts the browser's cookie store directly.
* **cookies.txt** – a Netscape-format file exported with a browser extension,
  useful when the browser is closed/locked or on a machine without keyring
  access.
"""

from __future__ import annotations

from pathlib import Path

# Browsers yt-dlp can read cookies from (see yt_dlp.cookies.SUPPORTED_BROWSERS).
SUPPORTED_BROWSERS: tuple[str, ...] = (
    "chrome",
    "chromium",
    "edge",
    "brave",
    "firefox",
    "opera",
    "vivaldi",
    "safari",
    "whale",
)

# Sites that realistically need cookies; used for the inline UI hint.
COOKIE_RECOMMENDED_HOSTS = ("facebook.com", "fb.watch", "instagram.com", "threads.net")


def needs_cookies(url: str) -> bool:
    lowered = (url or "").lower()
    return any(host in lowered for host in COOKIE_RECOMMENDED_HOSTS)


def cookie_options(browser: str = "", cookies_file: str = "") -> dict:
    """Build the yt-dlp options dict for the configured cookie source.

    An explicit ``cookies.txt`` wins over the browser setting because it is the
    more deliberate choice of the two.
    """
    if cookies_file and Path(cookies_file).expanduser().is_file():
        return {"cookiefile": str(Path(cookies_file).expanduser())}
    if browser and browser in SUPPORTED_BROWSERS:
        # (browser, profile, keyring, container) — None means "let yt-dlp decide".
        return {"cookiesfrombrowser": (browser, None, None, None)}
    return {}


def verify_browser_cookies(browser: str) -> tuple[bool, str]:
    """Try to actually load cookies so the UI can report success or the reason.

    Returns ``(ok, message)``. Import failures are common and benign (browser
    running with an encrypted store, no profile, unsupported OS), so the message
    is surfaced to the user rather than raised.
    """
    if browser not in SUPPORTED_BROWSERS:
        return False, f"Unsupported browser: {browser}"
    try:
        from yt_dlp.cookies import extract_cookies_from_browser

        jar = extract_cookies_from_browser(browser, logger=_SilentLogger())
        count = len(jar)
        if count == 0:
            return False, "No cookies found in this browser profile."
        return True, f"Imported {count} cookies from {browser}."
    except ImportError as exc:  # pragma: no cover - yt-dlp always ships this
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001 - yt-dlp raises many different types
        return False, f"{type(exc).__name__}: {exc}"


class _SilentLogger:
    """yt-dlp logger stub — cookie extraction is chatty and we only want the result."""

    def debug(self, msg: str) -> None:  # noqa: D102
        pass

    def info(self, msg: str) -> None:  # noqa: D102
        pass

    def warning(self, msg: str, only_once: bool = False) -> None:  # noqa: D102
        pass

    def error(self, msg: str) -> None:  # noqa: D102
        pass
