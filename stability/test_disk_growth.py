from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonClient  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("stability.test_disk_growth")


def _disk_usage_bytes(path: str = ".") -> int:
    p = subprocess.run(["du", "-sb", path], capture_output=True, text=True)  # noqa: S603,S607
    if p.returncode != 0:
        return 0
    try:
        return int(p.stdout.split()[0])
    except Exception:  # noqa: BLE001
        return 0


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    baseline = _disk_usage_bytes(".")

    # Run 200 executions including a disk-abusive payload to test cleanup behavior.
    disk_abuse = (
        "import os\n"
        "i = 0\n"
        "while i < 50:\n"
        "    with open(f'tmp_{i}.bin', 'wb') as f:\n"
        "        f.write(b'0' * 2_000_000)\n"
        "    i += 1\n"
        "print('DONE')\n"
    )

    for i in range(200):
        if i % 25 == 0:
            try:
                _ = client.execute("python", "3.10.0", disk_abuse, stdin="", args=[])
            except Exception:  # noqa: BLE001
                pass
        else:
            try:
                _ = client.execute("python", "3.10.0", 'print("OK")\n', stdin="", args=[])
            except Exception:  # noqa: BLE001
                pass

    after = _disk_usage_bytes(".")
    growth = after - baseline
    ok = growth < 200 * 1024 * 1024  # allow some noise, ensure no runaway growth

    test_name = "stability.test_disk_growth"
    mc.record(
        test_name=test_name,
        language="host",
        status="pass" if ok else "fail",
        latency_ms=0.0,
        error_type="" if ok else "disk_growth_exceeded",
        details={"baseline_disk_bytes": baseline, "after_disk_bytes": after, "growth_bytes": growth},
    )
    results: List[dict] = [mc.export()[-1]]

    out_path = write_results_json("stability_test_disk_growth.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s %s", "PASS" if ok else "FAIL", test_name)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

