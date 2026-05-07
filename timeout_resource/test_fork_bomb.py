from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("timeout_resource.test_fork_bomb")


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
    kill_window = float(os.getenv("ABUSE_KILL_WINDOW_SECONDS", "10"))
    os.environ["REQUEST_TIMEOUT_SECONDS"] = str(kill_window + 2)
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    # Attempt to fork rapidly; sandbox should block or kill.
    code = (
        "import os\n"
        "while True:\n"
        "    try:\n"
        "        os.fork()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    test_name = "timeout_resource.test_fork_bomb.python"

    start = time.perf_counter()
    ok = False
    error_type = ""
    details = {}
    try:
        pr = client.execute("python", "3.10.0", code, stdin="", args=[])
        elapsed = time.perf_counter() - start
        exit_code, stdout, stderr = _extract_run_fields(pr.data)
        ok = (elapsed <= kill_window) and (exit_code != 0)
        details = {
            "elapsed_s": elapsed,
            "http_latency_ms": pr.latency_ms,
            "exit_code": exit_code,
            "stdout_preview": stdout[:200],
            "stderr_preview": stderr[:500],
        }
        if not ok:
            error_type = "not_terminated_within_window"
    except PistonAPIError as e:
        elapsed = time.perf_counter() - start
        ok = (e.category == "timeout") and (elapsed <= kill_window + 2)
        error_type = "" if ok else e.category
        details = {"elapsed_s": elapsed, "error": str(e), "category": e.category}

    mc.record(
        test_name=test_name,
        language="python",
        status="pass" if ok else "fail",
        latency_ms=details.get("http_latency_ms", 0.0),
        error_type=error_type,
        details=details,
    )
    results = mc.export()
    out_path = write_results_json("timeout_resource_test_fork_bomb.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s %s", "PASS" if ok else "FAIL", test_name)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

