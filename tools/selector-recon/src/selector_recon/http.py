"""Shared HTTP layer: honest User-Agent, per-run cache, per-host rate limit, robots.txt."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from . import __version__

USER_AGENT = f"selector-recon/{__version__} (+https://github.com/landmark2436/osint_tools_claude)"
MAX_BODY_CHARS = 2_000_000

# Markers of bot challenges, CAPTCHAs and WAF block pages. Matched case-insensitively.
_BLOCK_MARKERS = (
    ("cf-chl", "Cloudflare challenge"),
    ("challenges.cloudflare.com", "Cloudflare challenge"),
    ("<title>just a moment...</title>", "Cloudflare challenge"),
    ("attention required! | cloudflare", "Cloudflare block page"),
    ("g-recaptcha", "reCAPTCHA"),
    ("h-captcha", "hCaptcha"),
    ("cf-turnstile", "Cloudflare Turnstile"),
    ("captcha-delivery.com", "DataDome challenge"),
    ("_incapsula_resource", "Imperva challenge"),
    ("px-captcha", "PerimeterX challenge"),
    ("awswaf", "AWS WAF challenge"),
)


@dataclass
class Response:
    url: str
    status: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""
    from_cache: bool = False


def detect_block(resp: Response) -> str | None:
    """Return a reason if the response looks like a CAPTCHA, bot challenge or rate limit."""
    if resp.status == 429:
        return "rate limited (HTTP 429)"
    head = resp.text[:20000].lower()
    for marker, reason in _BLOCK_MARKERS:
        if marker in head:
            return reason
    if resp.status in (403, 503) and resp.headers.get("server", "").lower() in ("cloudflare", "akamaighost"):
        return f"HTTP {resp.status} from {resp.headers['server']}"
    return None


class HttpClient:
    def __init__(
        self,
        timeout: float = 10.0,
        rate: float = 1.0,
        obey_robots: bool = False,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.min_interval = 1.0 / rate if rate > 0 else 0.0
        self.obey_robots = obey_robots
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self._cache: dict[tuple[str, str, str | None], Response] = {}
        self._cache_lock = threading.Lock()
        self._host_locks: dict[str, threading.Lock] = {}
        self._host_last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self.request_count = 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _host_lock(self, host: str) -> threading.Lock:
        with self._cache_lock:
            return self._host_locks.setdefault(host, threading.Lock())

    def _throttle(self, host: str) -> None:
        """Wait until this host may receive the next request. Caller holds the host lock."""
        wait = self._host_last.get(host, 0.0) + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._host_last[host] = time.monotonic()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: str | None = None,
        follow_redirects: bool = True,
        check_robots: bool | None = None,
    ) -> Response:
        """Send a request. Raises httpx.HTTPError on transport errors, PermissionError if robots.txt forbids it."""
        key = (method.upper(), url, data)
        with self._cache_lock:
            if key in self._cache:
                cached = self._cache[key]
                return Response(cached.url, cached.status, cached.text, cached.headers, cached.content, from_cache=True)
        if (self.obey_robots if check_robots is None else check_robots) and not self.robots_allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        host = urlsplit(url).netloc.lower()
        with self._host_lock(host):
            self._throttle(host)
            r = self._client.request(
                method, url, headers=headers, content=data, follow_redirects=follow_redirects
            )
            self.request_count += 1
        resp = Response(str(r.url), r.status_code, r.text[:MAX_BODY_CHARS], dict(r.headers), r.content[:MAX_BODY_CHARS * 4])
        with self._cache_lock:
            self._cache[key] = resp
        return resp

    def get(self, url: str, **kwargs: object) -> Response:
        return self.request("GET", url, **kwargs)  # type: ignore[arg-type]

    def robots_allowed(self, url: str) -> bool:
        """True if robots.txt allows our User-Agent to fetch url. A missing or unreadable robots.txt allows."""
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            parser: RobotFileParser | None = None
            try:
                r = self.request("GET", base + "/robots.txt", check_robots=False)
                if r.status == 200:
                    parser = RobotFileParser()
                    parser.parse(r.text.splitlines())
            except httpx.HTTPError:
                parser = None
            self._robots[base] = parser
        parser = self._robots[base]
        return parser is None or parser.can_fetch(USER_AGENT, url)
