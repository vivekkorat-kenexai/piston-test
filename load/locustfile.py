from __future__ import annotations

import os
import random
import time
from typing import Any, Dict

from dotenv import load_dotenv
from locust import HttpUser, between, task

from utils.data_generator import (  # type: ignore
    javascript_fibonacci,
    javascript_matrix_multiply,
    javascript_fizzbuzz,
    javascript_hello_world,
    python_fibonacci,
    python_matrix_multiply,
    python_fizzbuzz,
    python_hello_world,
)

load_dotenv()


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    exit_code = int(run.get("code", run.get("exit_code", 1)) or 1)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def _pick_language() -> str:
    # Mix via env override if needed; default 60/40
    py_pct = float(os.getenv("LOCUST_PYTHON_PERCENT", "60"))
    return "python" if random.random() < (py_pct / 100.0) else "javascript"


def _body_from_payload(p) -> Dict[str, Any]:
    return {
        "language": p.language,
        "version": p.version,
        "files": [{"name": "main", "content": p.code}],
        "stdin": p.stdin,
        "args": [],
    }


class BasePistonUser(HttpUser):
    wait_time = between(0.01, 0.2)

    def on_start(self) -> None:
        # Allow full URL base via PISTON_API_URL; Locust's host is used if set.
        piston_url = os.getenv("PISTON_API_URL")
        if piston_url:
            self.host = piston_url.rstrip("/")

    def _post_execute(self, body: Dict[str, Any], name: str) -> None:
        start = time.perf_counter()
        with self.client.post("/api/v2/execute", json=body, name=name, catch_response=True) as resp:
            latency_ms = (time.perf_counter() - start) * 1000.0
            if resp.status_code < 200 or resp.status_code >= 300:
                resp.failure(f"http_{resp.status_code}")
                return
            try:
                data = resp.json()
            except Exception as e:  # noqa: BLE001
                resp.failure(f"invalid_json:{e}")
                return
            exit_code, _stdout, stderr = _extract_run_fields(data if isinstance(data, dict) else {})
            if exit_code != 0 or stderr.strip():
                resp.failure("sandbox_error")
                return
            resp.success()
            # Attach custom-like info in response length fields (best-effort).
            resp.request_meta = getattr(resp, "request_meta", {})
            resp.request_meta["execution_latency"] = latency_ms


class LightUser(BasePistonUser):
    weight = 50

    @task
    def hello(self) -> None:
        lang = _pick_language()
        p = python_hello_world() if lang == "python" else javascript_hello_world()
        self._post_execute(_body_from_payload(p), name="LightUser/hello_world")


class MediumUser(BasePistonUser):
    weight = 35

    @task
    def medium(self) -> None:
        lang = _pick_language()
        p = python_fizzbuzz(20) if lang == "python" else javascript_fizzbuzz(20)
        self._post_execute(_body_from_payload(p), name="MediumUser/fizzbuzz")


class HeavyUser(BasePistonUser):
    weight = 15

    @task
    def heavy(self) -> None:
        lang = _pick_language()
        p = python_fibonacci(28) if lang == "python" else javascript_fibonacci(28)
        if random.random() < 0.5:
            p = python_matrix_multiply() if lang == "python" else javascript_matrix_multiply()
        self._post_execute(_body_from_payload(p), name="HeavyUser/heavy")

