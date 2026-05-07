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


log = get_logger("functional.test_async_polling")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    exit_code = int(run.get("code", run.get("exit_code", 1)) or 1)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


async def _one_execute(
    session: aiohttp.ClientSession,
    url: str,
    payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], float]:
    start = time.perf_counter()
    async with session.post(url, json=payload) as resp:
        data = await resp.json()
        latency_ms = (time.perf_counter() - start) * 1000.0
        if resp.status < 200 or resp.status >= 300:
            return {"http_status": resp.status, "data": data}, latency_ms
        return data, latency_ms


async def run() -> tuple[bool, List[dict]]:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000").rstrip("/")
    execute_url = f"{base_url}/api/v2/execute"
    timeout = aiohttp.ClientTimeout(total=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")))

    mc = MetricsCollector()
    results: List[dict] = []

    payloads = []
    for i in range(20):
        lang = "python" if i % 2 == 0 else "javascript"
        p = pick_payload(lang, "hello_world")
        payloads.append(
            {
                "language": p.language,
                "version": p.version,
                "files": [{"name": "main", "content": p.code}],
                "stdin": p.stdin,
                "args": [],
            }
        )

    overall_ok = True
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [asyncio.create_task(_one_execute(session, execute_url, body)) for body in payloads]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    for idx, item in enumerate(responses):
        test_name = f"functional.test_async_polling.req_{idx}"
        lang = payloads[idx]["language"]
        if isinstance(item, Exception):
            overall_ok = False
            mc.record(
                test_name=test_name,
                language=lang,
                status="fail",
                latency_ms=0.0,
                error_type=type(item).__name__,
                details={"error": str(item)},
            )
            results.append(mc.export()[-1])
            continue

        data, latency_ms = item
        exit_code, stdout, stderr = _extract_run_fields(data if isinstance(data, dict) else {})
        ok = (exit_code == 0) and (stderr.strip() == "")
        overall_ok = overall_ok and ok

        mc.record(
            test_name=test_name,
            language=lang,
            status="pass" if ok else "fail",
            latency_ms=latency_ms,
            error_type="" if ok else "nonzero_exit_or_stderr",
            details={
                "exit_code": exit_code,
                "stdout_preview": stdout[:500],
                "stderr_preview": stderr[:500],
            },
        )
        results.append(mc.export()[-1])

    return overall_ok, results


def main() -> int:
    ok, results = asyncio.run(run())
    out_path = write_results_json("functional_test_async_polling.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s functional.test_async_polling", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

