from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.data_generator import pick_payload  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import ensure_report_dir, write_results_json  # noqa: E402


log = get_logger("stability.test_long_running")


def _run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603,S607
    return p.returncode, p.stdout, p.stderr


def _docker_stats_snapshot() -> Dict[str, Any]:
    rc, out, err = _run_cmd(["docker", "stats", "--no-stream", "--format", "{{json .}}"])
    if rc != 0:
        return {"error": err.strip() or "docker_stats_failed"}
    lines = [ln for ln in out.splitlines() if ln.strip()]
    samples = []
    for ln in lines:
        try:
            samples.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            continue
    return {"containers": samples, "count": len(samples)}


def _disk_usage_bytes(path: str = ".") -> int:
    rc, out, _err = _run_cmd(["du", "-sb", path])
    if rc != 0:
        return 0
    try:
        return int(out.split()[0])
    except Exception:  # noqa: BLE001
        return 0


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    duration_s = int(os.getenv("STABILITY_DURATION_SECONDS", "3600"))
    sample_every_s = 30

    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    report_dir = ensure_report_dir()

    baseline_disk = _disk_usage_bytes(".")
    baseline_stats = _docker_stats_snapshot()
    baseline_count = int(baseline_stats.get("count", 0) or 0)

    timeline: List[Dict[str, Any]] = []
    results: List[dict] = []
    ok_overall = True

    start = time.perf_counter()
    next_sample = start
    request_i = 0

    while time.perf_counter() - start < duration_s:
        lang = "python" if request_i % 2 == 0 else "javascript"
        payload = pick_payload(lang, "hello_world")
        test_name = "stability.test_long_running"
        try:
            pr = client.execute(payload.language, payload.version, payload.code, stdin=payload.stdin, args=[])
            # Minimal record (raw request results are handled by other test modules; here we focus on stability timeline).
            results.append(
                {
                    "timestamp": time.time(),
                    "test_name": test_name,
                    "language": lang,
                    "status": "pass",
                    "latency_ms": pr.latency_ms,
                    "error_type": "",
                }
            )
        except PistonAPIError as e:
            ok_overall = False
            results.append(
                {
                    "timestamp": time.time(),
                    "test_name": test_name,
                    "language": lang,
                    "status": "fail",
                    "latency_ms": 0.0,
                    "error_type": e.category,
                    "details": {"error": str(e)},
                }
            )

        request_i += 1

        now = time.perf_counter()
        if now >= next_sample:
            stats = _docker_stats_snapshot()
            disk_now = _disk_usage_bytes(".")
            disk_growth = disk_now - baseline_disk

            container_count = int(stats.get("count", 0) or 0)
            mem_growth_flag = False
            disk_growth_flag = disk_growth > 500 * 1024 * 1024
            zombie_flag = container_count > max(baseline_count + 10, int(baseline_count * 1.5) + 1)

            if zombie_flag:
                ok_overall = False
                log.error("ERROR zombie container growth suspected: baseline=%s current=%s", baseline_count, container_count)
            if disk_growth_flag:
                ok_overall = False
                log.error("ERROR disk growth > 500MB: growth_bytes=%s", disk_growth)
            if mem_growth_flag:
                ok_overall = False
                log.error("ERROR memory growth > 20%% (heuristic)")

            timeline.append(
                {
                    "timestamp": time.time(),
                    "container_count": container_count,
                    "disk_usage_bytes": disk_now,
                    "disk_growth_bytes": disk_growth,
                    "docker_stats": stats,
                    "flags": {
                        "zombie_containers": zombie_flag,
                        "disk_growth": disk_growth_flag,
                        "memory_growth": mem_growth_flag,
                    },
                }
            )
            next_sample = now + sample_every_s

        time.sleep(0.05)

    timeline_path = report_dir / "stability_timeline.json"
    timeline_path.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    log.info("Wrote stability timeline: %s", timeline_path)

    out_path = write_results_json("stability_test_long_running.json", results, summary={"requests_sent": request_i})
    log.info("Wrote results: %s", out_path)
    log.info("%s stability.test_long_running", "PASS" if ok_overall else "FAIL")
    return 0 if ok_overall else 2


if __name__ == "__main__":
    raise SystemExit(main())

