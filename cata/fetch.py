from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .errors import Blocked, NotFound

BASE = "https://www.catawiki.com"
DEFAULT_CACHE = Path.home() / ".cata" / "cache"


class _RateLimiter:
    def __init__(self, per_second: float):
        self._min_gap = 1.0 / per_second if per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            gap = time.monotonic() - self._last
            if gap < self._min_gap:
                time.sleep(self._min_gap - gap)
            self._last = time.monotonic()


class Fetcher:
    def __init__(
        self,
        rate_per_second: float = 1.0,
        cache_ttl: int = 3600,
        cache_dir: Path | None = None,
        impersonate: str = "chrome",
        session=None,
        retries: int = 3,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl
        self.retries = retries
        self._limiter = _RateLimiter(rate_per_second)
        self._impersonate = impersonate
        self._session = session

    def _get_session(self):
        if self._session is None:
            from curl_cffi import requests

            self._session = requests.Session(impersonate=self._impersonate)
        return self._session

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def _read_cache(self, url: str, ttl: int) -> str | None:
        path = self._cache_path(url)
        if not path.exists() or ttl <= 0:
            return None
        if time.time() - path.stat().st_mtime > ttl:
            return None
        return json.loads(path.read_text())["body"]

    def _write_cache(self, url: str, body: str) -> None:
        self._cache_path(url).write_text(json.dumps({"url": url, "body": body}))

    def get(self, url: str, *, ttl: int | None = None) -> str:
        ttl = self.cache_ttl if ttl is None else ttl
        cached = self._read_cache(url, ttl)
        if cached is not None:
            return cached

        for attempt in range(self.retries + 1):
            self._limiter.wait()
            response = self._get_session().get(url, timeout=30)
            if response.status_code == 200:
                final = str(getattr(response, "url", url) or url)
                if "/l/" in url and "/l/" not in final:
                    raise NotFound(url)
                self._write_cache(url, response.text)
                return response.text
            if response.status_code == 404:
                raise NotFound(url)
            if attempt < self.retries:
                time.sleep(2**attempt)

        raise Blocked(url)

    def get_many(self, urls: list[str], *, concurrency: int = 4) -> list[str]:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            return list(pool.map(self.get, urls))
