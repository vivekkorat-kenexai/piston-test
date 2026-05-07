from __future__ import annotations

import asyncio
import os
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


log = get_logger("load.test_burst_traffic")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    code_val = run["code"] if "code" in run else run.get("exit_code", 1)
    exit_code = 1 if code_val is None else int(code_val)
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


async def run_burst() -> Tuple[bool, List[dict], Dict[str, int]]:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000").rstrip("/")
    url = f"{base_url}/api/v2/execute"
    request_timeout_s = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    timeout = aiohttp.ClientTimeout(total=request_timeout_s)

    mc = MetricsCollector()
    results: List[dict] = []
    error_counts: Dict[str, int] = {}

    bodies = []
    for i in range(200):
        lang = "python" if i % 2 == 0 else "javascript"
        p = pick_payload(lang, "hello_world")
        bodies.append(
            {
                "language": p.language,
                "version": p.version,
                "files": [{"name": "main", "content": p.code}],
                "stdin": p.stdin,
                "args": [],
            }
        )

    ok_overall = True
    async with aiohttp.ClientSession(timeout=timeout) as session:
        start = time.perf_counter()
        tasks = [asyncio.create_task(_one(session, url, body)) for body in bodies]
        done = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        log.info("Burst sent 200 requests in %.3fs", elapsed)

    for i, (ok, latency_ms, err) in enumerate(done):
        lang = bodies[i]["language"]
        ok_overall = ok_overall and ok
        if err:
            error_counts[err] = error_counts.get(err, 0) + 1
        mc.record(
            test_name=f"load.test_burst_traffic.req_{i}",
            language=lang,
            status="pass" if ok else "fail",
            latency_ms=latency_ms,
            error_type=err,
        )
        results.append(mc.export()[-1])

    return ok_overall, results, error_counts


def main() -> int:
    ok, results, error_counts = asyncio.run(run_burst())
    out_path = write_results_json("load_test_burst_traffic.json", results, summary={"error_breakdown": error_counts})
    log.info("Wrote results: %s", out_path)
    log.info("Error breakdown: %s", error_counts)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

