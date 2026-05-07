from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter


ALLOWED_RUNTIMES = {
    ("python", "3.10.0"),
    ("javascript", "18.15.0"),
}


class PistonAPIError(RuntimeError):
    def __init__(self, message: str, *, category: str, cause: Optional[BaseException] = None):
        super().__init__(message)
        self.category = category
        self.cause = cause


@dataclass(frozen=True)
class PistonResponse:
    data: Dict[str, Any]
    latency_ms: float


class PistonClient:
    def __init__(self, base_url: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key or os.getenv("PISTON_API_KEY", "")

        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.timeout_seconds = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=0)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        self._headers_lock = threading.Lock()
        self._default_headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        # Auth is out of scope for your current setup; we intentionally do not send api_key.

    def _request(self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None) -> PistonResponse:
        url = urljoin(self.base_url, path.lstrip("/"))

        last_exc: Optional[BaseException] = None
        for attempt in range(0, self.max_retries + 1):
            start = time.perf_counter()
            try:
                with self._headers_lock:
                    headers = dict(self._default_headers)
                resp = self._session.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=json_body,
                    timeout=self.timeout_seconds,
                )
                latency_ms = (time.perf_counter() - start) * 1000.0

                if resp.status_code < 200 or resp.status_code >= 300:
                    raise PistonAPIError(
                        f"HTTP {resp.status_code} from {path}",
                        category="http_error",
                    )
                try:
                    data = resp.json()
                except Exception as e:  # noqa: BLE001
                    raise PistonAPIError(
                        f"Invalid JSON response from {path}",
                        category="invalid_response",
                        cause=e,
                    ) from e

                return PistonResponse(data=data, latency_ms=latency_ms)
            except (requests.Timeout,) as e:
                last_exc = e
                category = "timeout"
            except (requests.ConnectionError,) as e:
                last_exc = e
                category = "connection"
            except PistonAPIError as e:
                last_exc = e
                category = e.category

            if attempt >= self.max_retries:
                break

            backoff = (2**attempt) * 0.4
            jitter = random.random() * 0.2
            time.sleep(backoff + jitter)

        raise PistonAPIError(
            f"Request failed after {self.max_retries + 1} attempts: {method} {path}",
            category="network_error" if not isinstance(last_exc, PistonAPIError) else last_exc.category,
            cause=last_exc,
        )

    def get_runtimes(self) -> PistonResponse:
        return self._request("GET", "/api/v2/runtimes")

    def execute(
        self,
        language: str,
        version: str,
        code: str,
        stdin: str = "",
        args: Optional[List[str]] = None,
    ) -> PistonResponse:
        if (language, version) not in ALLOWED_RUNTIMES:
            raise PistonAPIError(
                f"Unsupported runtime {language}@{version}. Allowed: python@3.10.0, javascript@18.15.0",
                category="invalid_request",
            )
        args = args or []

        body = {
            "language": language,
            "version": version,
            "files": [{"name": "main", "content": code}],
            "stdin": stdin or "",
            "args": args,
        }
        return self._request("POST", "/api/v2/execute", json_body=body)

