from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("security.test_container_escape")


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

    # Attempt to read through /proc/1/root which would indicate a host / init namespace escape.
    py_code = (
        "paths = ['/proc/1/cgroup','/proc/1/root/etc/hostname','/proc/1/root/etc/passwd']\n"
        "for p in paths:\n"
        "    try:\n"
        "        with open(p,'r') as f:\n"
        "            print(p + ':' + f.read(200).replace('\\n','\\\\n'))\n"
        "    except Exception as e:\n"
        "        print(p + ':ERROR:' + str(e))\n"
    )

    test_name = "security.test_container_escape.python"
    ok = False
    error_type = ""
    details = {}
    try:
        pr = client.execute("python", "3.10.0", py_code, stdin="", args=[])
        exit_code, stdout, stderr = _extract_run_fields(pr.data)
        combined = (stdout + "\n" + stderr).lower()
        # SECURITY FAIL if /proc/1/root/etc/hostname read succeeds (no ERROR marker).
        escape_possible = "/proc/1/root/etc/hostname:" in stdout and ":ERROR:" not in stdout.split("/proc/1/root/etc/hostname:")[-1][:50]
        blocked = ("permission" in combined) or ("denied" in combined) or (":error:" in combined) or (exit_code != 0)
        ok = blocked and not escape_possible
        details = {
            "exit_code": exit_code,
            "stdout_preview": stdout[:2000],
            "stderr_preview": stderr[:2000],
            "escape_possible": escape_possible,
        }
        if not ok:
            error_type = "container_escape_possible"
    except PistonAPIError as e:
        ok = False
        error_type = e.category
        details = {"error": str(e), "category": e.category}

    mc.record(
        test_name=test_name,
        language="python",
        status="pass" if ok else "fail",
        latency_ms=0.0,
        error_type=error_type,
        details=details,
    )
    results = mc.export()
    out_path = write_results_json("security_test_container_escape.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s %s", "SECURITY PASS" if ok else "SECURITY FAIL", test_name)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

