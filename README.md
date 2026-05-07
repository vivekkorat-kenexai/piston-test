## Piston API Enterprise Testing Suite

Production-ready functional, security, resource-abuse, load, stress, stability, monitoring, and reporting framework for a **self-hosted Piston API** instance serving **1000+ concurrent students** in an online examination platform.

### Architecture

```text
TestScripts  -->  PistonAPI  -->  DockerSandbox
```

### Prerequisites
- **Python**: 3.10+\n- **Docker**: required by Piston sandbox and stability checks\n- **k6**: for scripts under `stress/k6/`\n\n### Installation
From the repository root:
\n```bash
cd piston-test-suite
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp configs/.env.example .env
```
\nEdit `.env` and set `PISTON_API_URL` to your Piston instance.

### Verify Piston runtimes are available
\n```bash
curl -sS "$PISTON_API_URL/api/v2/runtimes" | head
```
\nEnsure **only these** are used by the suite:\n- `python` version `3.10.0`\n- `javascript` version `18.15.0`\n\n### Running tests by category
\n- **Functional**:\n```bash
python functional/test_basic_execution.py
python functional/test_stdin_stdout.py
python functional/test_error_handling.py
python functional/test_multi_language.py
python functional/test_async_polling.py
python functional/test_batch_execution.py
```\n\n- **Timeout & resource abuse**:\n```bash
python timeout_resource/test_infinite_loop.py
python timeout_resource/test_cpu_exhaustion.py
python timeout_resource/test_memory_abuse.py
python timeout_resource/test_disk_abuse.py
python timeout_resource/test_stdout_flood.py
python timeout_resource/test_fork_bomb.py
python timeout_resource/test_process_spawn.py
python timeout_resource/test_thread_explosion.py
```\n\n- **Security**:\n```bash
python security/test_filesystem_escape.py
python security/test_env_variable_leak.py
python security/test_network_access.py
python security/test_container_escape.py
python security/test_docker_socket_access.py
python security/test_subprocess_abuse.py
python security/test_privilege_escalation.py
```\n\n- **Load**:\n```bash
python load/test_exam_peak_simulation.py
python load/test_burst_traffic.py
python load/test_sustained_load.py
python load/test_multi_language_load.py
python load/test_concurrent_submissions.py
```\n\n- **Stress**:\n```bash
python stress/test_queue_overflow.py
k6 run stress/k6/exam_load_test.js
k6 run stress/k6/burst_test.js
```\n\n- **Stability**:\n```bash
python stability/test_zombie_containers.py
python stability/test_orphan_processes.py
python stability/test_memory_leak.py
python stability/test_disk_growth.py
python stability/test_long_running.py
```\n\n### Run the full suite
\n```bash
./run_all_tests.sh
```\n\nTo include the long-running stability test:\n```bash
RUN_STABILITY=true ./run_all_tests.sh
```\n\n### Reports\n- Raw JSON results are written to `REPORT_OUTPUT_DIR` (default `./reports`).\n- The suite generates:\n  - `analysis_summary.json`\n  - `report.html`\n  - `results_export.csv`\n  - `full_report.json`\n\nOpen the HTML report:\n```bash
xdg-open ./reports/report.html
```\n\n### Environment variables\n| Variable | Default | Meaning |\n|---|---:|---|\n| `PISTON_API_URL` | `http://localhost:2000` | Base URL for Piston API |\n| `PISTON_API_KEY` | empty | Accepted but unused in current setup |\n| `CONCURRENT_USERS` | `1000` | Concurrency for peak simulation/thread test |\n| `TEST_DURATION_SECONDS` | `300` | Duration for load tests |\n| `REQUESTS_PER_SECOND` | `50` | Target RPS for sustained load |\n| `REQUEST_TIMEOUT_SECONDS` | `30` | Per-request timeout |\n| `MAX_RETRIES` | `3` | Client retries (sync client) |\n| `STABILITY_DURATION_SECONDS` | `3600` | Duration for long-running stability |\n| `REPORT_OUTPUT_DIR` | `./reports` | Output directory for results |\n| `LOG_DIR` | `./logs` | Log output directory |\n| `LOG_LEVEL` | `INFO` | Logging verbosity |\n\n### Operational meaning of failures\n- **Functional failures**: Piston API is not reliably executing correct code; treat as service-impacting.\n- **Timeout/resource failures**: sandbox limits are too permissive or misconfigured; abuse can starve other students.\n- **Security failures**: sandbox isolation is insufficient; treat as critical.\n- **Load/stress failures**: capacity/queueing/backpressure issues; risk of exam-time outages.\n- **Stability failures**: possible zombie containers, resource leaks, or cleanup failures; risks long exam sessions.\n+
