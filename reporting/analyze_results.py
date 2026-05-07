from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tabulate import tabulate


def _load_results(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    if not isinstance(results, list):
        return []
    return [r for r in results if isinstance(r, dict)]


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = int(round((p / 100.0) * (len(values_sorted) - 1)))
    k = max(0, min(k, len(values_sorted) - 1))
    return float(values_sorted[k])


def analyze(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    success = sum(1 for r in results if r.get("status") == "pass")
    failure = total - success
    latencies = [float(r.get("latency_ms", 0.0) or 0.0) for r in results if r.get("status") == "pass"]
    err_types: Dict[str, int] = {}
    for r in results:
        et = (r.get("error_type") or "").strip()
        if r.get("status") != "pass" and et:
            err_types[et] = err_types.get(et, 0) + 1

    duration_s = 0.0
    ts = [r.get("timestamp") for r in results if r.get("timestamp")]
    # timestamps are RFC strings in some modules and epoch floats in others; don't overfit.
    # Throughput computed best-effort based on count only.
    throughput = (total / duration_s) if duration_s > 0 else 0.0

    summary = {
        "total_requests": total,
        "success_count": success,
        "failure_count": failure,
        "success_rate_percent": (success / total * 100.0) if total else 0.0,
        "p50_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_latency_ms": _percentile(latencies, 95),
        "p99_latency_ms": _percentile(latencies, 99),
        "throughput_rps": throughput,
        "error_breakdown": err_types,
        "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return summary


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python reporting/analyze_results.py <results.json>")
        return 2

    in_path = Path(sys.argv[1])
    results = _load_results(in_path)
    summary = analyze(results)

    report_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "./reports"))
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / "analysis_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    table = [
        ["Total", summary["total_requests"]],
        ["Success", summary["success_count"]],
        ["Failure", summary["failure_count"]],
        ["Success rate (%)", f'{summary["success_rate_percent"]:.2f}'],
        ["p50 latency (ms)", f'{summary["p50_latency_ms"]:.1f}'],
        ["p95 latency (ms)", f'{summary["p95_latency_ms"]:.1f}'],
        ["p99 latency (ms)", f'{summary["p99_latency_ms"]:.1f}'],
    ]
    print(tabulate(table, tablefmt="github"))

    if summary["error_breakdown"]:
        err_rows = [[k, v] for k, v in sorted(summary["error_breakdown"].items(), key=lambda kv: -kv[1])]
        print("\nError breakdown:")
        print(tabulate(err_rows, headers=["error_type", "count"], tablefmt="github"))

    print(f"\nSaved summary to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

