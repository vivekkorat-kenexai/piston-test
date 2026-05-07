from __future__ import annotations

import os
import resource
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonClient  # noqa: E402
from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("stability.test_memory_leak")


def _rss_kb() -> int:
    # ru_maxrss is KB on Linux
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    baseline = _rss_kb()
    for i in range(500):
        lang = "python" if i % 2 == 0 else "javascript"
        payload = pick_payload(lang, "hello_world")
        try:
            _ = client.execute(payload.language, payload.version, payload.code, stdin=payload.stdin, args=[])
        except Exception:  # noqa: BLE001
            pass

    after = _rss_kb()
    growth = after - baseline
    ok = growth <= int(baseline * 0.20) if baseline > 0 else True

    test_name = "stability.test_memory_leak"
    mc.record(
        test_name=test_name,
        language="runner",
        status="pass" if ok else "fail",
        latency_ms=0.0,
        error_type="" if ok else "memory_growth_exceeded",
        details={"baseline_rss_kb": baseline, "after_rss_kb": after, "growth_rss_kb": growth},
    )
    results: List[dict] = [mc.export()[-1]]

    out_path = write_results_json("stability_test_memory_leak.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s %s", "PASS" if ok else "FAIL", test_name)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

