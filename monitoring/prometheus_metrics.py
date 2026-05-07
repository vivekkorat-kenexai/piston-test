from __future__ import annotations

import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from utils.logger import get_logger


log = get_logger("monitoring.prometheus_metrics")


piston_execution_total = Counter(
    "piston_execution_total",
    "Total Piston executions recorded by test suite",
    ["language", "status"],
)

piston_execution_latency_seconds = Histogram(
    "piston_execution_latency_seconds",
    "Piston execution latency (seconds)",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 8, 15, 30),
)

piston_active_executions = Gauge(
    "piston_active_executions",
    "Active in-flight executions tracked by exporter",
)

piston_error_total = Counter(
    "piston_error_total",
    "Total errors recorded by test suite",
    ["error_type"],
)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return
        data = generate_latest()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return


def start_server(port: int = 9100) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info("Prometheus metrics server listening on :%s", port)
    return server


def record_execution(language: str, status: str, latency_ms: float, error_type: str = "") -> None:
    piston_execution_total.labels(language=language, status=status).inc()
    piston_execution_latency_seconds.observe(max(0.0, latency_ms / 1000.0))
    if error_type:
        piston_error_total.labels(error_type=error_type).inc()


def main() -> int:
    port = int(os.getenv("PROMETHEUS_PORT", "9100"))
    _ = start_server(port)
    while True:
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())

