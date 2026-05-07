from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiohttp
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("load.test_sustained_load")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    code_val = run["code"] if "code" in run else run.get("exit_code", 1)
    exit_code = 1 if code_val is None else int(code_val)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


@dataclass
class TokenBucket:
    rate_per_s: float
    capacity: float
    tokens: float = 0.0
    last: float = 0.0

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last = time.perf_counter()

    async def take(self, n: float = 1.0) -> None:
        while True:
            now = time.perf_counter()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_s)
            if self.tokens >= n:
                self.tokens -= n
                return
            await asyncio.sleep(max(0.001, (n - self.tokens) / max(self.rate_per_s, 0.001)))


async def _one(session: aiohttp.ClientSession, url: str, body: Dict[str, Any]) -> Tuple[bool, float, str]:
    start = time.perf_counter()
    try:
        async with session.post(url, json=body) as resp:
            data = await resp.json()
            latency_ms = (time.perf_counter() - start) * 1000.0
            if resp.status < 200 or resp.status >= 300:
                return False, latency_ms, f"http_{resp.status}"
            exit_code, _stdout, stderr = _extract_run_fields(data if isinstance(data, dict) else {})
            ok = exit_code == 0 and stderr.strip() == ""
            return ok, latency_ms, "" if ok else "sandbox_error"
    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, "client_timeout"
    except Exception as e:  # noqa: BLE001
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, type(e).__name__


async def run_sustained() -> Tuple[Dict[str, Any], List[dict]]:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000").rstrip("/")
    url = f"{base_url}/api/v2/execute"
    duration_s = int(os.getenv("TEST_DURATION_SECONDS", "300"))
    rps = float(os.getenv("REQUESTS_PER_SECOND", "50"))
    request_timeout_s = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

    timeout = aiohttp.ClientTimeout(total=request_timeout_s)
    connector = aiohttp.TCPConnector(limit=200, ttl_dns_cache=60)
    bucket = TokenBucket(rate_per_s=rps, capacity=max(1.0, rps))

    mc = MetricsCollector()
    results: List[dict] = []
    latencies: List[float] = []

    sent = 0
    failures = 0
    start = time.perf_counter()
    end = start + duration_s

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        while time.perf_counter() < end:
            await bucket.take(1.0)
            lang = "python" if sent % 2 == 0 else "javascript"
            payload = pick_payload(lang, "hello_world")
            body = {
                "language": payload.language,
                "version": payload.version,
                "files": [{"name": "main", "content": payload.code}],
                "stdin": payload.stdin,
                "args": [],
            }
            ok, latency_ms, err = await _one(session, url, body)
            sent += 1
            if ok:
                latencies.append(latency_ms)
            else:
                failures += 1
            mc.record(
                test_name="load.test_sustained_load",
                language=lang,
                status="pass" if ok else "fail",
                latency_ms=latency_ms,
                error_type=err,
                details={"request_index": sent},
            )
            results.append(mc.export()[-1])

    total_time = time.perf_counter() - start
    summary = {
        "total_requests_sent": sent,
        "error_rate_percent": (failures / sent * 100.0) if sent else 0.0,
        "p50_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_latency_ms": sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else 0.0,
        "p99_latency_ms": sorted(latencies)[int(0.99 * (len(latencies) - 1))] if latencies else 0.0,
        "throughput_rps": sent / total_time if total_time > 0 else 0.0,
        "duration_seconds": duration_s,
        "target_rps": rps,
    }
    return summary, results


def main() -> int:
    summary, results = asyncio.run(run_sustained())
    out_path = write_results_json("load_test_sustained_load.json", results, summary=summary)
    log.info("Wrote results: %s", out_path)
    log.info("Summary: %s", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

