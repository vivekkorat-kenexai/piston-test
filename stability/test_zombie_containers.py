from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("stability.test_zombie_containers")


def _docker_ps_all() -> List[Dict[str, Any]]:
    p = subprocess.run(  # noqa: S603,S607
        ["docker", "ps", "-a", "--format", "{{.ID}} {{.Status}} {{.Image}} {{.Names}}"],
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        return [{"error": p.stderr.strip() or "docker_ps_failed"}]
    items = []
    for ln in p.stdout.splitlines():
        parts = ln.split(maxsplit=3)
        if len(parts) < 2:
            continue
        items.append({"id": parts[0], "status": parts[1], "raw": ln})
    return items


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    results = []
    overall_ok = True

    # Run 100 mixed executions (some light, some abusive).
    for i in range(100):
        lang = "python" if i % 2 == 0 else "javascript"
        payload = pick_payload(lang, "hello_world")
        try:
            _ = client.execute(payload.language, payload.version, payload.code, stdin=payload.stdin, args=[])
        except PistonAPIError:
            pass

    # Allow cleanup window.
    time.sleep(5)
    start = time.perf_counter()
    zombies: List[Dict[str, Any]] = []
    while time.perf_counter() - start < 60:
        items = _docker_ps_all()
        zombies = [x for x in items if isinstance(x, dict) and "Exited" in x.get("raw", "")]
        if not zombies:
            break
        time.sleep(5)

    ok = not zombies
    overall_ok = overall_ok and ok
    test_name = "stability.test_zombie_containers"
    mc.record(
        test_name=test_name,
        language="docker",
        status="pass" if ok else "fail",
        latency_ms=0.0,
        error_type="" if ok else "zombie_containers_detected",
        details={"zombie_count": len(zombies), "zombies": zombies[:50]},
    )
    results.append(mc.export()[-1])

    out_path = write_results_json("stability_test_zombie_containers.json", results)
    log.info("Wrote results: %s", out_path)
    log.info("%s %s", "PASS" if ok else "FAIL", test_name)
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

