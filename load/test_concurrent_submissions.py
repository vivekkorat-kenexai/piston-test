from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("load.test_concurrent_submissions")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    exit_code = int(run.get("code", run.get("exit_code", 1)) or 1)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    concurrent = int(os.getenv("CONCURRENT_USERS", "1000"))

    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    results = []
    overall_ok = True

    def worker(i: int) -> tuple[bool, float, str, str]:
        lang = "python" if i % 2 == 0 else "javascript"
        payload = pick_payload(lang, "hello_world")
        try:
            pr = client.execute(payload.language, payload.version, payload.code, stdin=payload.stdin, args=[])
            exit_code, _stdout, stderr = _extract_run_fields(pr.data)
            ok = exit_code == 0 and stderr.strip() == ""
            return ok, pr.latency_ms, "" if ok else "sandbox_error", lang
        except PistonAPIError as e:
            return False, 0.0, e.category, lang

    with ThreadPoolExecutor(max_workers=concurrent) as ex:
        futures = [ex.submit(worker, i) for i in range(concurrent)]
        for i, fut in enumerate(as_completed(futures)):
            ok, latency_ms, err, lang = fut.result()
            test_name = f"load.test_concurrent_submissions.req_{i}"
            overall_ok = overall_ok and ok
            mc.record(
                test_name=test_name,
                language=lang,
                status="pass" if ok else "fail",
                latency_ms=latency_ms,
                error_type=err,
            )
            results.append(mc.export()[-1])

    out_path = write_results_json("load_test_concurrent_submissions.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s load.test_concurrent_submissions", "PASS" if overall_ok else "FAIL")
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

