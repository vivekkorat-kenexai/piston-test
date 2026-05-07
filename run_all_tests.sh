#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${ROOT_DIR}/configs/.env.example" && ! -f "${ROOT_DIR}/.env" ]]; then
  echo "INFO: No .env found in ${ROOT_DIR}. You can copy configs/.env.example to .env"
fi

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

PISTON_API_URL="${PISTON_API_URL:-http://localhost:2000}"
REPORT_OUTPUT_DIR="${REPORT_OUTPUT_DIR:-./reports}"
RUN_STABILITY="${RUN_STABILITY:-false}"

mkdir -p "${ROOT_DIR}/${REPORT_OUTPUT_DIR}" "${ROOT_DIR}/${LOG_DIR:-./logs}"

echo "Checking Piston API reachability at ${PISTON_API_URL}/api/v2/runtimes"
curl -fsS "${PISTON_API_URL%/}/api/v2/runtimes" >/dev/null
echo "OK: Piston API reachable"

cd "${ROOT_DIR}"

FAIL=0

run_py () {
  local script="$1"
  echo "==> Running ${script}"
  if python "${script}"; then
    echo "PASS: ${script}"
  else
    echo "FAIL: ${script}"
    FAIL=1
  fi
}

run_py functional/test_basic_execution.py
run_py functional/test_stdin_stdout.py
run_py functional/test_error_handling.py
run_py functional/test_multi_language.py
run_py functional/test_async_polling.py
run_py functional/test_batch_execution.py

run_py timeout_resource/test_infinite_loop.py
run_py timeout_resource/test_cpu_exhaustion.py
run_py timeout_resource/test_memory_abuse.py
run_py timeout_resource/test_disk_abuse.py
run_py timeout_resource/test_stdout_flood.py
run_py timeout_resource/test_fork_bomb.py
run_py timeout_resource/test_process_spawn.py
run_py timeout_resource/test_thread_explosion.py

run_py security/test_filesystem_escape.py
run_py security/test_env_variable_leak.py
run_py security/test_network_access.py
run_py security/test_container_escape.py
run_py security/test_docker_socket_access.py
run_py security/test_subprocess_abuse.py
run_py security/test_privilege_escalation.py

run_py load/test_exam_peak_simulation.py

if [[ "${RUN_STABILITY}" == "true" ]]; then
  run_py stability/test_long_running.py
fi

echo "==> Reporting"
# Prefer analyzing the peak simulation output if present.
ANALYZE_INPUT="${REPORT_OUTPUT_DIR}/load_test_exam_peak_simulation.json"
if [[ ! -f "${ANALYZE_INPUT}" ]]; then
  # fallback: basic functional results
  ANALYZE_INPUT="${REPORT_OUTPUT_DIR}/functional_test_basic_execution.json"
fi
python reporting/analyze_results.py "${ANALYZE_INPUT}"
python reporting/generate_html_report.py "${ANALYZE_INPUT}"
python reporting/generate_csv_export.py "${ANALYZE_INPUT}"
python reporting/generate_json_report.py "${ANALYZE_INPUT}"

echo
if [[ "${FAIL}" -eq 0 ]]; then
  echo "FINAL RESULT: PASS"
  exit 0
else
  echo "FINAL RESULT: FAIL"
  exit 2
fi

