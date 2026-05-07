from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from jinja2 import Template

from reporting.analyze_results import analyze


HTML_TEMPLATE = Template(
    """<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>Piston Test Suite Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
      .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; }
      h1 { margin-top: 0; }
      code { background: #f6f6f6; padding: 2px 4px; border-radius: 4px; }
    </style>
  </head>
  <body>
    <h1>Piston API Enterprise Test Suite</h1>
    <p>Generated at <code>{{ generated_at }}</code></p>
    <div class="grid">
      <div class="card">
        <h2>Summary</h2>
        <ul>
          <li>Total requests: <b>{{ summary.total_requests }}</b></li>
          <li>Success rate: <b>{{ '%.2f'|format(summary.success_rate_percent) }}%</b></li>
          <li>p50 latency: <b>{{ '%.1f'|format(summary.p50_latency_ms) }} ms</b></li>
          <li>p95 latency: <b>{{ '%.1f'|format(summary.p95_latency_ms) }} ms</b></li>
          <li>p99 latency: <b>{{ '%.1f'|format(summary.p99_latency_ms) }} ms</b></li>
        </ul>
      </div>
      <div class="card">
        <h2>Error breakdown</h2>
        <canvas id="errChart"></canvas>
      </div>
    </div>

    <div class="card" style="margin-top:18px;">
      <h2>Latency distribution (ms)</h2>
      <canvas id="latChart"></canvas>
    </div>

    <script>
      const errLabels = {{ err_labels|safe }};
      const errValues = {{ err_values|safe }};
      new Chart(document.getElementById('errChart'), {
        type: 'pie',
        data: { labels: errLabels, datasets: [{ data: errValues }] },
      });

      const latLabels = {{ lat_labels|safe }};
      const latValues = {{ lat_values|safe }};
      new Chart(document.getElementById('latChart'), {
        type: 'bar',
        data: { labels: latLabels, datasets: [{ label: 'count', data: latValues }] },
        options: { scales: { y: { beginAtZero: true } } }
      });
    </script>
  </body>
</html>"""
)


def _build_latency_hist(latencies):
    if not latencies:
        return ["0-1000"], [0]
    buckets = [0, 250, 500, 1000, 2000, 5000, 10000, 30000]
    counts = [0 for _ in range(len(buckets) - 1)]
    for v in latencies:
        for i in range(len(buckets) - 1):
            if buckets[i] <= v < buckets[i + 1]:
                counts[i] += 1
                break
    labels = [f"{buckets[i]}-{buckets[i+1]}" for i in range(len(buckets) - 1)]
    return labels, counts


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python reporting/generate_html_report.py <results.json>")
        return 2

    in_path = Path(sys.argv[1])
    payload = json.loads(in_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []
    summary = analyze(results)

    err = summary.get("error_breakdown", {}) or {}
    err_labels = list(err.keys()) if err else ["none"]
    err_values = list(err.values()) if err else [1]

    latencies = [float(r.get("latency_ms", 0.0) or 0.0) for r in results if isinstance(r, dict) and r.get("status") == "pass"]
    lat_labels, lat_values = _build_latency_hist(latencies)

    out_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "./reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "report.html"

    html = HTML_TEMPLATE.render(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        summary=summary,
        err_labels=json.dumps(err_labels),
        err_values=json.dumps(err_values),
        lat_labels=json.dumps(lat_labels),
        lat_values=json.dumps(lat_values),
    )
    out_path.write_text(html, encoding="utf-8")
    print(f"Saved HTML report to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

