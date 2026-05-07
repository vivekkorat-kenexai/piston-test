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


log = get_logger("stress.test_queue_overflow")


async def _one(session: aiohttp.ClientSession, url: str, body: Dict[str, Any]) -> Tuple[bool, float, str]:
    start = time.perf_counter()
    try:
        async with session.post(url, json=body) as resp:
            _ = await resp.text()
            latency_ms = (time.perf_counter() - start) * 1000.0
            if resp.status >= 200 and resp.status < 300:
                return True, latency_ms, ""
            return False, latency_ms, f"http_{resp.status}"
    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, "client_timeout"
    except Exception as e:  # noqa: BLE001
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, latency_ms, type(e).__name__


async def run_overflow() -> Tuple[bool, List[dict], Dict[str, int]]:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000").rstrip("/")
    execute_url = f"{base_url}/api/v2/execute"
    runtimes_url = f"{base_url}/api/v2/runtimes"

    request_timeout_s = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    timeout = aiohttp.ClientTimeout(total=request_timeout_s)
    connector = aiohttp.TCPConnector(limit=2000, ttl_dns_cache=60)

    mc = MetricsCollector()
    results: List[dict] = []
    error_counts: Dict[str, int] = {}

    flood = int(os.getenv("QUEUE_OVERFLOW_REQUESTS", "2000"))

    bodies = []
    for i in range(flood):
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

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [asyncio.create_task(_one(session, execute_url, body)) for body in bodies]
        done = await asyncio.gather(*tasks)

        for i, (ok, latency_ms, err) in enumerate(done):
            if err:
                error_counts[err] = error_counts.get(err, 0) + 1
            mc.record(
                test_name=f"stress.test_queue_overflow.req_{i}",
                language=bodies[i]["language"],
                status="pass" if ok else "fail",
                latency_ms=latency_ms,
                error_type=err,
            )
            results.append(mc.export()[-1])

        # Assert API does not hard-crash: keep checking runtimes for 30s.
        healthy = True
        start = time.perf_counter()
        while time.perf_counter() - start < 30:
            try:
                async with session.get(runtimes_url) as resp:
                    if resp.status < 200 or resp.status >= 300:
                        healthy = False
            except Exception:  # noqa: BLE001
                healthy = False
            await asyncio.sleep(2)

    ok_overall = healthy
    if not healthy:
        error_counts["post_flood_unhealthy"] = error_counts.get("post_flood_unhealthy", 0) + 1
    return ok_overall, results, error_counts


def main() -> int:
    ok, results, error_counts = asyncio.run(run_overflow())
    out_path = write_results_json("stress_test_queue_overflow.json", results, summary={"error_breakdown": error_counts})
    log.info("Wrote results: %s", out_path)
    log.info("Observed errors: %s", error_counts)
    log.info("%s stress.test_queue_overflow", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

