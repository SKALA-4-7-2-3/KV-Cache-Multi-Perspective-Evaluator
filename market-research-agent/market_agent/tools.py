"""시도 단위 예산과 Tavily 경계. 제공자 응답의 비밀값은 오류에 노출하지 않는다."""

import ipaddress
import threading
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from .schemas import Limits


class ProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable=False, fatal=False):
        super().__init__(code)
        self.code, self.retryable, self.fatal = code, retryable, fatal


class BudgetExceeded(ProviderError):
    def __init__(self, kind):
        super().__init__(f"budget_exhausted:{kind}")


class Budget:
    def __init__(self, limits: Limits):
        self.limits = limits.model_dump()
        self.used = dict.fromkeys(self.limits, 0)
        self.events = []
        self.progress = {}
        self._lock = threading.Lock()

    def remaining(self, kind):
        with self._lock:
            return max(0, self.limits[kind] - self.used[kind])

    def constrain(self, limits: Limits):
        """시장 역할에 배정된 예산을 축소한다. 이전 회차 사용량은 유지한다."""
        with self._lock:
            for kind, value in limits.model_dump().items():
                self.limits[kind] = min(self.limits[kind], value)

    def take(self, kind):
        with self._lock:
            if self.used[kind] >= self.limits[kind]:
                raise BudgetExceeded(kind)
            self.used[kind] += 1

    def call(self, kind, operation, *, max_attempts=2):
        attempts = min(2, max_attempts)
        if attempts < 1:
            raise BudgetExceeded(kind)
        for attempt in range(attempts):
            self.take(kind)
            started = time.monotonic()
            event = {"kind": kind, "attempt": attempt + 1, "at": datetime.now(timezone.utc).isoformat()}
            try:
                result = operation()
                event["status"] = "ok"
                return result
            except ProviderError as exc:
                event.update(status="error", code=exc.code)
                if not exc.retryable or attempt == attempts - 1:
                    raise
            except Exception as exc:
                event.update(status="error", code=type(exc).__name__)
                raise ProviderError(f"provider_error:{type(exc).__name__}") from None
            finally:
                event["seconds"] = round(time.monotonic() - started, 3)
                self.events.append(event)


def public_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            return False
        host = p.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return not any(c.isspace() for c in host)
    except ValueError:
        return False


def canonical_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def published_date(value) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        try:
            return parsedate_to_datetime(value).date()
        except (ValueError, TypeError):
            return None


class TavilyWeb:
    def __init__(self, api_key: str, *, client=None):
        if not api_key:
            raise ProviderError("missing_tavily_key", fatal=True)
        self._key = api_key
        self._client = client or httpx.Client(timeout=20, follow_redirects=False)
        self._owns_client = client is None

    def close(self):
        if self._owns_client:
            self._client.close()

    def _post(self, endpoint, payload):
        try:
            response = self._client.post(f"https://api.tavily.com/{endpoint}", json=payload,
                headers={"Authorization": f"Bearer {self._key}"}, timeout=20)
        except (httpx.TimeoutException, httpx.TransportError):
            raise ProviderError("tavily_transport", retryable=True) from None
        status = response.status_code
        if status != 200:
            raise ProviderError(f"tavily_http_{status}", retryable=status in {408, 429, 500, 502, 503, 504},
                fatal=status in {401, 403, 432, 433})
        try:
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise ValueError()
            return data
        except ValueError:
            raise ProviderError("tavily_invalid_response") from None

    def search(self, query: str, as_of: date):
        data = self._post("search", {"query": query, "topic": "general", "search_depth": "basic",
            "max_results": 3, "include_answer": False, "include_raw_content": False,
            "end_date": as_of.isoformat(), "include_published_date": True})
        result = []
        for row in data["results"][:3]:
            if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ["url", "title", "content"]):
                raise ProviderError("tavily_invalid_search_item")
            if public_url(row["url"]):
                result.append({"url": canonical_url(row["url"]), "title": row["title"],
                    "content": row["content"], "published_at": published_date(row.get("published_date"))})
        return result

    def extract(self, url: str):
        if not public_url(url):
            raise ProviderError("unsafe_source_url")
        data = self._post("extract", {"urls": [url], "extract_depth": "basic", "format": "markdown", "timeout": 20})
        for row in data["results"]:
            if (isinstance(row, dict) and row.get("url") and canonical_url(row["url"]) == canonical_url(url)
                    and isinstance(row.get("raw_content"), str) and row["raw_content"].strip()):
                return row["raw_content"]
        raise ProviderError("extract_failed")
