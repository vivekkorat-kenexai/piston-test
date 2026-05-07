## Piston API Enterprise Testing Suite

Production-ready functional, security, resource-abuse, load, stress, stability, monitoring, and reporting framework for a **self-hosted Piston API** instance serving **1000+ concurrent students** in an online examination platform.

### Architecture

```text
TestScripts  -->  PistonAPI  -->  DockerSandbox
```

### Prerequisites

- **Python**: 3.10+
- **Docker**: required by Piston sandbox and stability checks
- **k6**: for scripts under `stress/k6/`

### Installation

From the repository root:

```bash
cd piston-test-suite
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp configs/.env.example .env
```

Edit `.env` and set `PISTON_API_URL` to your Piston instance.

### Verify Piston runtimes are available

```bash
curl -sS "$PISTON_API_URL/api/v2/runtimes" | head
```

Ensure **only these** are used by the suite:

- `python` version `3.10.0`
- `javascript` version `18.15.0`

### Running tests by category

- **Functional**:

```bash
python functional/test_basic_execution.py
python functional/test_stdin_stdout.py
python functional/test_error_handling.py
python functional/test_multi_language.py
python functional/test_async_polling.py
python functional/test_batch_execution.py
```

- **Timeout & resource abuse**:

```bash
python timeout_resource/test_infinite_loop.py
python timeout_resource/test_cpu_exhaustion.py
python timeout_resource/test_memory_abuse.py
python timeout_resource/test_disk_abuse.py
python timeout_resource/test_stdout_flood.py
python timeout_resource/test_fork_bomb.py
python timeout_resource/test_process_spawn.py
python timeout_resource/test_thread_explosion.py
```

- **Security**:

```bash
python security/test_filesystem_escape.py
python security/test_env_variable_leak.py
python security/test_network_access.py
python security/test_container_escape.py
python security/test_docker_socket_access.py
python security/test_subprocess_abuse.py
python security/test_privilege_escalation.py
```

- **Load**:

```bash
python load/test_exam_peak_simulation.py
python load/test_burst_traffic.py
python load/test_sustained_load.py
python load/test_multi_language_load.py
python load/test_concurrent_submissions.py
```

- **Stress**:

```bash
python stress/test_queue_overflow.py
k6 run stress/k6/exam_load_test.js
k6 run stress/k6/burst_test.js
```

- **Stability**:

```bash
python stability/test_zombie_containers.py
python stability/test_orphan_processes.py
python stability/test_memory_leak.py
python stability/test_disk_growth.py
python stability/test_long_running.py
```

### Run the full suite

```bash
./run_all_tests.sh
```

To include the long-running stability test:

```bash
RUN_STABILITY=true ./run_all_tests.sh
```

### Reports

- Raw JSON results are written to `REPORT_OUTPUT_DIR` (default `./reports`).
- The suite generates:
  - `analysis_summary.json`
  - `report.html`
  - `results_export.csv`
  - `full_report.json`

Open the HTML report:

```bash
xdg-open ./reports/report.html
```

### Environment variables

| Variable | Default | Meaning |
|---|---:|---|
| `PISTON_API_URL` | `http://localhost:2000` | Base URL for Piston API |
| `PISTON_API_KEY` | empty | Accepted but unused in current setup |
| `CONCURRENT_USERS` | `1000` | Concurrency for peak simulation/thread test |
| `TEST_DURATION_SECONDS` | `300` | Duration for load tests |
| `REQUESTS_PER_SECOND` | `50` | Target RPS for sustained load |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `MAX_RETRIES` | `3` | Client retries (sync client) |
| `STABILITY_DURATION_SECONDS` | `3600` | Duration for long-running stability |
| `REPORT_OUTPUT_DIR` | `./reports` | Output directory for results |
| `LOG_DIR` | `./logs` | Log output directory |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### What failures mean operationally

- **Functional failures**: Piston is not reliably executing correct code; exam submissions may fail or grade incorrectly.
- **Timeout/resource failures**: sandbox limits are too permissive/misconfigured; abusive submissions can starve other students.
- **Security failures**: sandbox isolation is insufficient; treat as critical.
- **Load/stress failures**: capacity/queueing/backpressure issues; risk of exam-time outages.
- **Stability failures**: zombie containers/resource leaks/cleanup failures; risks long exam sessions.
