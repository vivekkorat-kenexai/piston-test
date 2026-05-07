from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("functional.test_stdin_stdout")


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

    cases = [
        ("stdin_echo", "Echo multi-line stdin"),
        ("sort_array", "Sort array from stdin"),
    ]

    for lang in ("python", "javascript"):
        for payload_name, _desc in cases:
            payload = pick_payload(lang, payload_name)
            test_name = f"functional.test_stdin_stdout.{lang}.{payload_name}"
            try:
                pr = client.execute(payload.language, payload.version, payload.code, stdin=payload.stdin, args=[])
                exit_code, stdout, stderr = _extract_run_fields(pr.data)

                ok = exit_code == 0 and (payload.expected_stdout == stdout) and (stderr.strip() == "")
                status = "pass" if ok else "fail"
                overall_ok = overall_ok and ok

                mc.record(
                    test_name=test_name,
                    language=lang,
                    status=status,
                    latency_ms=pr.latency_ms,
                    error_type="",
                    details={
                        "exit_code": exit_code,
                        "expected_stdout_preview": (payload.expected_stdout or "")[:2000],
                        "stdout_preview": stdout[:2000],
                        "stderr_preview": stderr[:2000],
                    },
                )
                results.append(mc.export()[-1])

                log.info("%s %s", "PASS" if ok else "FAIL", test_name)
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
                log.error("FAIL %s (error_type=%s): %s", test_name, e.category, e)

    out_path = write_results_json("functional_test_stdin_stdout.json", results)
    log.info("Wrote results: %s", out_path)
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

