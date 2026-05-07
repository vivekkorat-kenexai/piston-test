from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("security.test_privilege_escalation")


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

    py_code = (
        "import os\n"
        "try:\n"
        "    os.setuid(0)\n"
        "    print('PRIV_ESC_OK')\n"
        "except Exception as e:\n"
        "    print('PRIV_ESC_BLOCKED:' + str(e))\n"
    )

    test_name = "security.test_privilege_escalation.python"
    ok = False
    error_type = ""
    details = {}
    try:
        pr = client.execute("python", "3.10.0", py_code, stdin="", args=[])
        exit_code, stdout, stderr = _extract_run_fields(pr.data)
        combined = (stdout + "\n" + stderr).lower()
        blocked = ("priv_esc_blocked" in combined) or ("permission" in combined) or ("operation not permitted" in combined) or (exit_code != 0)
        ok = blocked and ("priv_esc_ok" not in combined)
        details = {"exit_code": exit_code, "stdout_preview": stdout[:2000], "stderr_preview": stderr[:2000]}
        if not ok:
            error_type = "privilege_escalation_possible"
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
    out_path = write_results_json("security_test_privilege_escalation.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s %s", "SECURITY PASS" if ok else "SECURITY FAIL", test_name)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

