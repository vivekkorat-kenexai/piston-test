from __future__ import annotations

import asyncio
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiohttp
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from student_cases.test_student_algorithms import (  # noqa: E402
    _javascript_solution_bundle,
    _python_solution_bundle,
    _testcases,
)
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("load.test_student_cases_load")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    code_val = run["code"] if "code" in run else run.get("exit_code", 1)
    exit_code = 1 if code_val is None else int(code_val)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def _body(language: str, code: str, stdin: str) -> Dict[str, Any]:
    return {
        "language": language,
        "version": "3.10.0" if language == "python" else "18.15.0",
        "files": [{"name": "main", "content": code}],
        "stdin": stdin,
        "args": [],
    }


async def _one(session: aiohttp.ClientSession, url: str, body: Dict[str, Any], expected: str) -> Tuple[bool, float, str]:
    start = time.perf_counter()
    try:
        async with session.post(url, json=body) as resp:
            data = await resp.json()
            latency_ms = (time.perf_counter() - start) * 1000.0
            if resp.status < 200 or resp.status >= 300:
                return False, latency_ms, f"http_{resp.status}"
            exit_code, stdout, stderr = _extract_run_fields(data if isinstance(data, dict) else {})
            if exit_code != 0 or stderr.strip():
                return False, latency_ms, "sandbox_error"
            if stdout != expected:
                return False, latency_ms, "bad_output"
            return True, latency_ms, ""
    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, "client_timeout"
    except Exception as e:  # noqa: BLE001
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, type(e).__name__


async def run_load() -> Tuple[Dict[str, Any], List[dict]]:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000").rstrip("/")
    url = f"{base_url}/api/v2/execute"
    concurrent = int(os.getenv("CONCURRENT_USERS", "200"))
    duration_s = int(os.getenv("TEST_DURATION_SECONDS", "60"))
    request_timeout_s = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

    py_code = _python_solution_bundle()
    js_code = _javascript_solution_bundle()
    cases = _testcases()

    mc = MetricsCollector()
    results: List[dict] = []
    latencies: List[float] = []
    sent = 0
    ok_count = 0
    err_counts: Dict[str, int] = {}

    timeout = aiohttp.ClientTimeout(total=request_timeout_s)
    connector = aiohttp.TCPConnector(limit=concurrent, ttl_dns_cache=60)

    end = time.perf_counter() + duration_s
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        while time.perf_counter() < end:
            batch = []
            meta = []
            for _ in range(concurrent):
                language = "python" if random.random() < 0.6 else "javascript"
                idx = random.randrange(0, len(cases))
                _op, stdin, expected = cases[idx]
                code = py_code if language == "python" else js_code
                batch.append(_body(language, code, stdin))
                meta.append((language, idx, expected))

            tasks = [asyncio.create_task(_one(session, url, batch[i], meta[i][2])) for i in range(len(batch))]
            done = await asyncio.gather(*tasks)
            sent += len(done)

            for i, (ok, latency_ms, err) in enumerate(done):
                language, case_idx, _expected = meta[i]
                if ok:
                    ok_count += 1
                    latencies.append(latency_ms)
                else:
                    err_counts[err] = err_counts.get(err, 0) + 1
                mc.record(
                    test_name="load.test_student_cases_load",
                    language=language,
                    status="pass" if ok else "fail",
                    latency_ms=latency_ms,
                    error_type=err,
                    details={"case_index": case_idx},
                )
                results.append(mc.export()[-1])

            await asyncio.sleep(0.05)

    summary = {
        "total_requests_sent": sent,
        "success_rate_percent": (ok_count / sent * 100.0) if sent else 0.0,
        "error_breakdown": err_counts,
        "concurrent_users": concurrent,
        "duration_seconds": duration_s,
        "p50_latency_ms": sorted(latencies)[len(latencies) // 2] if latencies else 0.0,
        "p95_latency_ms": sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else 0.0,
        "p99_latency_ms": sorted(latencies)[int(0.99 * (len(latencies) - 1))] if latencies else 0.0,
    }
    return summary, results


def main() -> int:
    summary, results = asyncio.run(run_load())
    out_path = write_results_json("load_test_student_cases_load.json", results, summary=summary)
    log.info("Wrote results: %s", out_path)
    log.info("Summary: %s", summary)
    return 0 if summary["success_rate_percent"] >= 95.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

