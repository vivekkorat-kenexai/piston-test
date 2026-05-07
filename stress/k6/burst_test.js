import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

export const piston_execution_latency = new Trend('piston_execution_latency');
export const piston_error_rate = new Rate('piston_error_rate');

const BASE_URL = __ENV.PISTON_API_URL || 'http://localhost:2000';

export const options = {
  stages: [
    { duration: '10s', target: 1000 },
    { duration: '30s', target: 1000 },
    { duration: '5s', target: 0 },
  ],
};

function payload() {
  if (Math.random() < 0.5) {
    return {
      language: 'python',
      version: '3.10.0',
      files: [{ name: 'main', content: 'print("HELLO_FROM_PYTHON")\n' }],
      stdin: '',
      args: [],
    };
  }
  return {
    language: 'javascript',
    version: '18.15.0',
    files: [{ name: 'main', content: 'console.log("HELLO_FROM_JAVASCRIPT");\n' }],
    stdin: '',
    args: [],
  };
}

export default function () {
  const res = http.post(`${BASE_URL}/api/v2/execute`, JSON.stringify(payload()), {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  });
  piston_execution_latency.add(res.timings.duration);
  const ok = check(res, { 'status is 2xx': (r) => r.status >= 200 && r.status < 300 });
  piston_error_rate.add(!ok);
  sleep(0.05);
}

