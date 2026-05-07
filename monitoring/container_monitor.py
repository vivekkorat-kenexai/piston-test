from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from utils.logger import get_logger


log = get_logger("monitoring.container_monitor")


def main() -> int:
    log_dir = Path(os.getenv("LOG_DIR", "./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    out_path = log_dir / "container_stats.jsonl"

    interval_s = int(os.getenv("CONTAINER_MONITOR_INTERVAL_SECONDS", "10"))

    log.info("Writing docker stats to %s every %ss", out_path, interval_s)
    with out_path.open("a", encoding="utf-8") as f:
        while True:
            p = subprocess.run(  # noqa: S603,S607
                ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
            )
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if p.returncode != 0:
                rec = {"timestamp": ts, "error": p.stderr.strip() or "docker_stats_failed"}
                f.write(json.dumps(rec) + "\n")
                f.flush()
                time.sleep(interval_s)
                continue

            for ln in p.stdout.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except Exception:  # noqa: BLE001
                    obj = {"raw": ln}
                obj["timestamp"] = ts
                f.write(json.dumps(obj) + "\n")
            f.flush()
            time.sleep(interval_s)


if __name__ == "__main__":
    raise SystemExit(main())

