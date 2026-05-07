from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python reporting/generate_csv_export.py <results.json>")
        return 2

    in_path = Path(sys.argv[1])
    payload = json.loads(in_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []

    out_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "./reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results_export.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "language", "test_name", "latency_ms", "status", "error_type"])
        for r in results:
            if not isinstance(r, dict):
                continue
            w.writerow(
                [
                    r.get("timestamp", ""),
                    r.get("language", ""),
                    r.get("test_name", ""),
                    r.get("latency_ms", ""),
                    r.get("status", ""),
                    r.get("error_type", ""),
                ]
            )

    print(f"Saved CSV export to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

