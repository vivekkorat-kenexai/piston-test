from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.data_generator import javascript_fizzbuzz, python_fizzbuzz  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("functional.test_multi_language")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    code_val = run["code"] if "code" in run else run.get("exit_code", 1)
    exit_code = 1 if code_val is None else int(code_val)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    overall_ok = True
    results = []

    py = python_fizzbuzz(50)
    js = javascript_fizzbuzz(50)
    test_name = "functional.test_multi_language.fizzbuzz"

    try:
        pr_py = client.execute(py.language, py.version, py.code, stdin=py.stdin, args=[])
        pr_js = client.execute(js.language, js.version, js.code, stdin=js.stdin, args=[])
        exit_py, out_py, err_py = _extract_run_fields(pr_py.data)
        exit_js, out_js, err_js = _extract_run_fields(pr_js.data)

        ok = (
            exit_py == 0
            and exit_js == 0
            and err_py.strip() == ""
            and err_js.strip() == ""
            and out_py == out_js
        )
        status = "pass" if ok else "fail"
        overall_ok = overall_ok and ok

        mc.record(
            test_name=test_name,
            language="python+javascript",
            status=status,
            latency_ms=max(pr_py.latency_ms, pr_js.latency_ms),
            error_type="",
            details={
                "python_latency_ms": pr_py.latency_ms,
                "javascript_latency_ms": pr_js.latency_ms,
                "python_exit_code": exit_py,
                "javascript_exit_code": exit_js,
                "stdout_equal": out_py == out_js,
                "stdout_preview": out_py[:2000],
                "python_stderr_preview": err_py[:2000],
                "javascript_stderr_preview": err_js[:2000],
            },
        )
        results.append(mc.export()[-1])

        log.info("%s %s", "PASS" if ok else "FAIL", test_name)
    except PistonAPIError as e:
        overall_ok = False
        mc.record(
            test_name=test_name,
            language="python+javascript",
            status="fail",
            latency_ms=0.0,
            error_type=e.category,
            details={"error": str(e)},
        )
        results.append(mc.export()[-1])
        log.error("FAIL %s (error_type=%s): %s", test_name, e.category, e)

    out_path = write_results_json("functional_test_multi_language.json", results)
    log.info("Wrote results: %s", out_path)
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

