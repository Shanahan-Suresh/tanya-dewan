"""Polite, cached HTTP: every URL is downloaded once, one request at a time per host."""

import hashlib
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

import certifi
import httpx

from . import config

_last_request: dict[str, float] = {}
_client: httpx.Client | None = None


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    if config.EXTRA_CA.exists():
        ctx.load_verify_locations(str(config.EXTRA_CA))
    return ctx


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            verify=_ssl_context(),
            timeout=config.TIMEOUT_S,
            headers={"User-Agent": config.USER_AGENT},
            follow_redirects=True,
        )
    return _client


def cache_path(url: str) -> Path:
    """Cache file for a URL: data/cache/<host>/<sha1 of the URL><extension>."""
    parts = urlsplit(url)
    suffix = Path(parts.path).suffix.lower()
    if suffix not in {".pdf", ".xml", ".html", ".json"}:
        suffix = ".bin"
    name = hashlib.sha1(url.encode("utf-8")).hexdigest() + suffix
    return config.CACHE / parts.netloc / name


def _wait_turn(host: str) -> None:
    gap = time.monotonic() - _last_request.get(host, 0.0)
    if gap < config.MIN_INTERVAL_S:
        time.sleep(config.MIN_INTERVAL_S - gap)
    _last_request[host] = time.monotonic()


def get(url: str, *, refresh: bool = False) -> bytes:
    """Return the body of `url`, from the cache when it holds the file.

    `refresh` re-downloads, for listing pages that change (never for a sitting's PDF).
    Raises httpx.HTTPStatusError on a 4xx or 5xx answer; nothing is cached then.
    """
    path = cache_path(url)
    if path.exists() and not refresh:
        return path.read_bytes()
    _wait_turn(urlsplit(url).netloc)
    response = client().get(url)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(response.content)
    tmp.replace(path)
    return response.content


def head(url: str) -> httpx.Response:
    """One HEAD request (not cached), for publish dates and sizes."""
    _wait_turn(urlsplit(url).netloc)
    return client().head(url)
