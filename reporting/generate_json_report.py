from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reporting.analyze_results import analyze  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python reporting/generate_json_report.py <results.json>")
        return 2

    in_path = Path(sys.argv[1])
    payload = json.loads(in_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    summary = analyze(results if isinstance(results, list) else [])

    out_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "./reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "full_report.json"

    out_payload: Dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_file": str(in_path),
        "summary": summary,
        "results": results,
    }
    out_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
    print(f"Saved JSON report to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

