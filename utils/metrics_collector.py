from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_report_dir() -> Path:
    report_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "./reports"))
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_results_json(filename: str, results: List[Dict[str, Any]], summary: Optional[Dict[str, Any]] = None) -> Path:
    report_dir = ensure_report_dir()
    path = report_dir / filename
    payload: Dict[str, Any] = {"generated_at": _now_ts(), "results": results}
    if summary is not None:
        payload["summary"] = summary
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return path


@dataclass
class MetricsCollector:
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _events: List[Dict[str, Any]] = field(default_factory=list, init=False)

    def record(
        self,
        *,
        test_name: str,
        language: str,
        status: str,
        latency_ms: float,
        error_type: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "timestamp": _now_ts(),
            "test_name": test_name,
            "language": language,
            "status": status,
            "latency_ms": float(latency_ms),
            "error_type": error_type or "",
        }
        if details:
            event["details"] = details
        with self._lock:
            self._events.append(event)

    def export(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events)

