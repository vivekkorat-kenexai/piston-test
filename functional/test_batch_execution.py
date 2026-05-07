from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("functional.test_batch_execution")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    exit_code = int(run.get("code", run.get("exit_code", 1)) or 1)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    total = 50
    total_start = time.perf_counter()
    overall_ok = True
    results = []
    latencies = []

    for i in range(total):
        lang = "python" if i % 2 == 0 else "javascript"
        payload = pick_payload(lang, "hello_world")
        test_name = f"functional.test_batch_execution.{lang}.req_{i}"
        try:
            pr = client.execute(payload.language, payload.version, payload.code, stdin=payload.stdin, args=[])
            exit_code, stdout, stderr = _extract_run_fields(pr.data)
            ok = (exit_code == 0) and (stderr.strip() == "")
            overall_ok = overall_ok and ok
            latencies.append(pr.latency_ms)

            mc.record(
                test_name=test_name,
                language=lang,
                status="pass" if ok else "fail",
                latency_ms=pr.latency_ms,
                error_type="" if ok else "nonzero_exit_or_stderr",
                details={
                    "exit_code": exit_code,
                    "stdout_preview": stdout[:200],
                    "stderr_preview": stderr[:200],
                },
            )
            results.append(mc.export()[-1])
        except PistonAPIError as e:
            overall_ok = False
            mc.record(
                test_name=test_name,
                language=lang,
                status="fail",
                latency_ms=0.0,
                error_type=e.category,
                details={"error": str(e)},
            )
            results.append(mc.export()[-1])

    total_ms = (time.perf_counter() - total_start) * 1000.0
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
    summary = {"total_requests": total, "total_time_ms": total_ms, "avg_latency_ms": avg_latency}

    out_path = write_results_json("functional_test_batch_execution.json", results, summary=summary)
    log.info("Wrote results: %s", out_path)
    log.info("%s functional.test_batch_execution (total_ms=%.1f, avg_latency_ms=%.1f)", "PASS" if overall_ok else "FAIL", total_ms, avg_latency)
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

