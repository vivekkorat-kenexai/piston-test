from __future__ import annotations

import asyncio
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiohttp
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("load.test_multi_language_load")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    exit_code = int(run.get("code", run.get("exit_code", 1)) or 1)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


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


async def run_alt() -> Tuple[Dict[str, Any], List[dict]]:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000").rstrip("/")
    url = f"{base_url}/api/v2/execute"
    duration_s = int(os.getenv("TEST_DURATION_SECONDS", "300"))
    request_timeout_s = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

    timeout = aiohttp.ClientTimeout(total=request_timeout_s)
    connector = aiohttp.TCPConnector(limit=200, ttl_dns_cache=60)

    mc = MetricsCollector()
    results: List[dict] = []
    py_lat: List[float] = []
    js_lat: List[float] = []

    start = time.perf_counter()
    end = start + duration_s
    i = 0
    failures = 0

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        while time.perf_counter() < end:
            lang = "python" if i % 2 == 0 else "javascript"
            payload = pick_payload(lang, "hello_world")
            body = {
                "language": payload.language,
                "version": payload.version,
                "files": [{"name": "main", "content": payload.code}],
                "stdin": payload.stdin,
                "args": [],
            }
            ok, latency_ms, err = await _one(session, url, body)
            if not ok:
                failures += 1
            if lang == "python":
                py_lat.append(latency_ms)
            else:
                js_lat.append(latency_ms)
            mc.record(
                test_name="load.test_multi_language_load",
                language=lang,
                status="pass" if ok else "fail",
                latency_ms=latency_ms,
                error_type=err,
                details={"request_index": i},
            )
            results.append(mc.export()[-1])
            i += 1

    def med(xs: List[float]) -> float:
        return statistics.median(xs) if xs else 0.0

    summary = {
        "python_median_latency_ms": med(py_lat),
        "javascript_median_latency_ms": med(js_lat),
        "latency_ratio_js_over_py": (med(js_lat) / med(py_lat)) if med(py_lat) > 0 else 0.0,
        "total_requests_sent": i,
        "failure_count": failures,
    }
    return summary, results


def main() -> int:
    summary, results = asyncio.run(run_alt())
    out_path = write_results_json("load_test_multi_language_load.json", results, summary=summary)
    log.info("Wrote results: %s", out_path)
    # Soft assert: "similar latency profiles" => ratio within 1.5x
    ratio = float(summary.get("latency_ratio_js_over_py", 0.0))
    ok = ratio == 0.0 or ratio <= 1.5
    log.info("%s load.test_multi_language_load (ratio=%.2f)", "PASS" if ok else "FAIL", ratio)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

