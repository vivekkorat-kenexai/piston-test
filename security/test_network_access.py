from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("security.test_network_access")


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
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://1.1.1.1', timeout=3).read(50)\n"
        "    print('NETWORK_OK')\n"
        "except Exception as e:\n"
        "    print('NETWORK_BLOCKED:' + str(e))\n"
    )

    js_code = (
        "async function main(){\n"
        "  try {\n"
        "    const res = await fetch('http://1.1.1.1', { signal: AbortSignal.timeout(3000) });\n"
        "    await res.text();\n"
        "    console.log('NETWORK_OK');\n"
        "  } catch (e) {\n"
        "    console.log('NETWORK_BLOCKED:' + String(e));\n"
        "  }\n"
        "}\n"
        "main();\n"
    )

    overall_ok = True
    results = []

    for lang, version, code in (
        ("python", "3.10.0", py_code),
        ("javascript", "18.15.0", js_code),
    ):
        test_name = f"security.test_network_access.{lang}"
        ok = False
        error_type = ""
        details = {}
        try:
            pr = client.execute(lang, version, code, stdin="", args=[])
            exit_code, stdout, stderr = _extract_run_fields(pr.data)
            combined = (stdout + "\n" + stderr).lower()
            blocked = ("network_blocked" in combined) or ("refused" in combined) or ("timed out" in combined) or (exit_code != 0)
            ok = blocked and ("network_ok" not in combined)
            details = {
                "exit_code": exit_code,
                "stdout_preview": stdout[:2000],
                "stderr_preview": stderr[:2000],
            }
            if not ok:
                error_type = "network_access_possible"
        except PistonAPIError as e:
            ok = False
            error_type = e.category
            details = {"error": str(e), "category": e.category}

        overall_ok = overall_ok and ok
        mc.record(
            test_name=test_name,
            language=lang,
            status="pass" if ok else "fail",
            latency_ms=0.0,
            error_type=error_type,
            details=details,
        )
        results.append(mc.export()[-1])
        log.info("%s %s", "SECURITY PASS" if ok else "SECURITY FAIL", test_name)

    out_path = write_results_json("security_test_network_access.json", results)
    log.info("Wrote results: %s", out_path)
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

