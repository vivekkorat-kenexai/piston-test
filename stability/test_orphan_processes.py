from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List, Set

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonClient  # noqa: E402
from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("stability.test_orphan_processes")


def _snapshot_pids() -> Set[int]:
    pids: Set[int] = set()
    for name in os.listdir("/proc"):
        if name.isdigit():
            pids.add(int(name))
    return pids


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    before = _snapshot_pids()

    for i in range(100):
        lang = "python" if i % 2 == 0 else "javascript"
        payload = pick_payload(lang, "hello_world")
        try:
            _ = client.execute(payload.language, payload.version, payload.code, stdin=payload.stdin, args=[])
        except Exception:  # noqa: BLE001
            pass

    time.sleep(5)
    after = _snapshot_pids()

    # Heuristic: report any new PIDs still present (may include unrelated system changes).
    new_pids = sorted(list(after - before))

    ok = len(new_pids) < 50  # soft threshold; adjust in your environment
    test_name = "stability.test_orphan_processes"
    mc.record(
        test_name=test_name,
        language="host",
        status="pass" if ok else "fail",
        latency_ms=0.0,
        error_type="" if ok else "orphan_processes_suspected",
        details={"new_pid_count": len(new_pids), "new_pids_sample": new_pids[:200]},
    )
    results: List[dict] = [mc.export()[-1]]

    out_path = write_results_json("stability_test_orphan_processes.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s %s", "PASS" if ok else "FAIL", test_name)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

