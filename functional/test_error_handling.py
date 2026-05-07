from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("functional.test_error_handling")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    exit_code = int(run.get("code", run.get("exit_code", 1)) or 1)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def _cases_for(language: str) -> list[tuple[str, str]]:
    if language == "python":
        return [
            ("syntax_error", "def oops(:\n    pass\n"),
            ("runtime_error", "print(1/0)\n"),
            ("name_error", "print(not_defined_variable)\n"),
        ]
    if language == "javascript":
        return [
            ("syntax_error", "function oops( { console.log('x'); }\n"),
            ("runtime_error", "console.log(1/0); throw new Error('boom');\n"),
            ("name_error", "console.log(notDefinedVariable);\n"),
        ]
    raise ValueError(f"Unsupported language: {language}")


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    overall_ok = True
    results = []

    for lang, version in (("python", "3.10.0"), ("javascript", "18.15.0")):
        for case_name, code in _cases_for(lang):
            test_name = f"functional.test_error_handling.{lang}.{case_name}"
            try:
                pr = client.execute(lang, version, code, stdin="", args=[])
                exit_code, stdout, stderr = _extract_run_fields(pr.data)

                ok = (exit_code != 0) and bool(stderr.strip())
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

    out_path = write_results_json("functional_test_error_handling.json", results)
    log.info("Wrote results: %s", out_path)
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

