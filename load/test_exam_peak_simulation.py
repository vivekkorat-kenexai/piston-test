from __future__ import annotations

import asyncio
import math
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiohttp
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.data_generator import (  # noqa: E402
    javascript_fibonacci,
    javascript_hello_world,
    javascript_matrix_multiply,
    javascript_fizzbuzz,
    python_fibonacci,
    python_hello_world,
    python_matrix_multiply,
    python_fizzbuzz,
)
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("load.test_exam_peak_simulation")


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values_sorted[int(k)])
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return float(d0 + d1)


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    code_val = run["code"] if "code" in run else run.get("exit_code", 1)
    exit_code = 1 if code_val is None else int(code_val)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def _build_payload_mix() -> List[Tuple[str, str]]:
    # Returns list of (language, complexity) where complexity is "light" or "heavy".
    mix: List[Tuple[str, str]] = []
    # Language mix: 60% python, 40% js. Complexity mix: 70% light, 30% heavy.
    for _ in range(100):
        lang = "python" if random.random() < 0.60 else "javascript"
        complexity = "light" if random.random() < 0.70 else "heavy"
        mix.append((lang, complexity))
    return mix


def _pick_payload(lang: str, complexity: str) -> Dict[str, Any]:
    if lang == "python":
        if complexity == "light":
            p = python_hello_world() if random.random() < 0.5 else python_fizzbuzz(20)
        else:
            p = python_fibonacci(28) if random.random() < 0.5 else python_matrix_multiply()
    else:
        if complexity == "light":
            p = javascript_hello_world() if random.random() < 0.5 else javascript_fizzbuzz(20)
        else:
            p = javascript_fibonacci(28) if random.random() < 0.5 else javascript_matrix_multiply()
    return {
        "language": p.language,
        "version": p.version,
        "files": [{"name": "main", "content": p.code}],
        "stdin": p.stdin,
        "args": [],
        "_expected_stdout": p.expected_stdout,
        "_payload_name": p.name,
    }


async def _one(
    session: aiohttp.ClientSession,
    url: str,
    body: Dict[str, Any],
    request_timeout_s: float,
) -> Tuple[bool, float, str]:
    # returns (success, latency_ms, error_type)
    start = time.perf_counter()
    try:
        async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=request_timeout_s)) as resp:
            data = await resp.json()
            latency_ms = (time.perf_counter() - start) * 1000.0
            if resp.status < 200 or resp.status >= 300:
                return False, latency_ms, f"http_{resp.status}"
            exit_code, stdout, stderr = _extract_run_fields(data if isinstance(data, dict) else {})
            if exit_code != 0 or stderr.strip():
                return False, latency_ms, "sandbox_error"
            expected = body.get("_expected_stdout")
            if expected is not None and expected not in stdout:
                return False, latency_ms, "bad_output"
            return True, latency_ms, ""
    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, "client_timeout"
    except Exception as e:  # noqa: BLE001
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, type(e).__name__


async def run_peak() -> Tuple[Dict[str, Any], List[dict]]:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000").rstrip("/")
    url = f"{base_url}/api/v2/execute"

    concurrent_users = int(os.getenv("CONCURRENT_USERS", "1000"))
    duration_s = int(os.getenv("TEST_DURATION_SECONDS", "300"))
    request_timeout_s = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

    mc = MetricsCollector()
    results: List[dict] = []

    mix = _build_payload_mix()
    start_time = time.perf_counter()
    end_time = start_time + duration_s

    timeout = aiohttp.ClientTimeout(total=request_timeout_s)
    connector = aiohttp.TCPConnector(limit=concurrent_users, ttl_dns_cache=60)

    sent = 0
    successes = 0
    failures = 0
    timeouts = 0
    latencies: List[float] = []
    error_counts: Dict[str, int] = {}

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        while time.perf_counter() < end_time:
            batch_start = time.perf_counter()
            bodies = []
            for i in range(concurrent_users):
                lang, complexity = mix[(sent + i) % len(mix)]
                bodies.append(_pick_payload(lang, complexity))

            tasks = [asyncio.create_task(_one(session, url, body, request_timeout_s)) for body in bodies]
            sent += len(tasks)
            completed = await asyncio.gather(*tasks)

            for idx, (ok, latency_ms, err) in enumerate(completed):
                body = bodies[idx]
                lang = body["language"]
                test_name = "load.test_exam_peak_simulation"
                status = "pass" if ok else "fail"
                if ok:
                    successes += 1
                    latencies.append(latency_ms)
                else:
                    failures += 1
                    error_counts[err] = error_counts.get(err, 0) + 1
                    if err == "client_timeout":
                        timeouts += 1

                mc.record(
                    test_name=test_name,
                    language=lang,
                    status=status,
                    latency_ms=latency_ms,
                    error_type=err,
                    details={"payload": body.get("_payload_name"), "complexity": "unknown"},
                )
                results.append(mc.export()[-1])

            # Yield a bit to avoid tight loop if server is extremely fast.
            elapsed_batch = time.perf_counter() - batch_start
            if elapsed_batch < 0.1:
                await asyncio.sleep(0.05)

    total_time = time.perf_counter() - start_time
    rps = sent / total_time if total_time > 0 else 0.0
    peak_rps = rps  # conservative; batch-based approach

    summary = {
        "total_requests_sent": sent,
        "success_rate_percent": (successes / sent * 100.0) if sent else 0.0,
        "error_rate_percent": (failures / sent * 100.0) if sent else 0.0,
        "timeout_rate_percent": (timeouts / sent * 100.0) if sent else 0.0,
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "p99_latency_ms": _percentile(latencies, 99),
        "peak_requests_per_second": peak_rps,
        "error_breakdown": error_counts,
        "duration_seconds": duration_s,
        "concurrent_users": concurrent_users,
    }
    return summary, results


def main() -> int:
    summary, results = asyncio.run(run_peak())
    out_path = write_results_json("load_test_exam_peak_simulation.json", results, summary=summary)
    log.info("Wrote results: %s", out_path)
    log.info(
        "Peak summary: total=%s success_rate=%.2f%% p95=%.1fms p99=%.1fms peak_rps=%.1f",
        summary["total_requests_sent"],
        summary["success_rate_percent"],
        summary["p95_latency_ms"],
        summary["p99_latency_ms"],
        summary["peak_requests_per_second"],
    )
    return 0 if summary["error_rate_percent"] < 5.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

