from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.api_client import PistonAPIError, PistonClient  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from utils.metrics_collector import MetricsCollector, write_results_json  # noqa: E402


log = get_logger("student_cases.test_student_algorithms")


def _extract_run_fields(resp_json: dict) -> tuple[int, str, str]:
    run = resp_json.get("run") or resp_json.get("result") or {}
    code_val = run["code"] if "code" in run else run.get("exit_code", 1)
    exit_code = 1 if code_val is None else int(code_val)
    stdout = run.get("stdout", "") or ""
    stderr = run.get("stderr", "") or ""
    return exit_code, stdout, stderr


def _python_solution_bundle() -> str:
    # Intentionally "student style": straightforward, a bit verbose, but correct.
    return (
        "import sys\n"
        "\n"
        "def reverse_string(s: str) -> str:\n"
        "    return s[::-1]\n"
        "\n"
        "def is_palindrome(s: str) -> str:\n"
        "    t = ''.join(ch.lower() for ch in s if ch.isalnum())\n"
        "    return 'true' if t == t[::-1] else 'false'\n"
        "\n"
        "def two_sum(nums, target):\n"
        "    seen = {}\n"
        "    for i, x in enumerate(nums):\n"
        "        if target - x in seen:\n"
        "            return [seen[target - x], i]\n"
        "        seen[x] = i\n"
        "    return [-1, -1]\n"
        "\n"
        "def valid_parentheses(s: str) -> str:\n"
        "    st = []\n"
        "    m = {')':'(',']':'[','}':'{'}\n"
        "    for ch in s:\n"
        "        if ch in '([{':\n"
        "            st.append(ch)\n"
        "        elif ch in m:\n"
        "            if not st or st[-1] != m[ch]:\n"
        "                return 'false'\n"
        "            st.pop()\n"
        "    return 'true' if not st else 'false'\n"
        "\n"
        "def group_anagrams(words):\n"
        "    mp = {}\n"
        "    for w in words:\n"
        "        key = ''.join(sorted(w))\n"
        "        mp.setdefault(key, []).append(w)\n"
        "    # stable output: sort groups and words\n"
        "    groups = [sorted(v) for v in mp.values()]\n"
        "    groups.sort(key=lambda g: (len(g), g[0] if g else ''))\n"
        "    return groups\n"
        "\n"
        "def merge_intervals(intervals):\n"
        "    intervals.sort()\n"
        "    res = []\n"
        "    for a, b in intervals:\n"
        "        if not res or a > res[-1][1]:\n"
        "            res.append([a, b])\n"
        "        else:\n"
        "            res[-1][1] = max(res[-1][1], b)\n"
        "    return res\n"
        "\n"
        "def coin_change(coins, amount):\n"
        "    INF = 10**9\n"
        "    dp = [0] + [INF] * amount\n"
        "    for a in range(1, amount + 1):\n"
        "        best = INF\n"
        "        for c in coins:\n"
        "            if a - c >= 0:\n"
        "                best = min(best, dp[a - c] + 1)\n"
        "        dp[a] = best\n"
        "    return -1 if dp[amount] >= INF else dp[amount]\n"
        "\n"
        "def main():\n"
        "    data = sys.stdin.read().splitlines()\n"
        "    if not data:\n"
        "        return\n"
        "    op = data[0].strip()\n"
        "    if op == 'reverse':\n"
        "        s = data[1] if len(data) > 1 else ''\n"
        "        print(reverse_string(s))\n"
        "    elif op == 'palindrome':\n"
        "        s = data[1] if len(data) > 1 else ''\n"
        "        print(is_palindrome(s))\n"
        "    elif op == 'two_sum':\n"
        "        nums = [int(x) for x in data[1].split()] if len(data) > 1 else []\n"
        "        target = int(data[2]) if len(data) > 2 else 0\n"
        "        ans = two_sum(nums, target)\n"
        "        print(f\"{ans[0]} {ans[1]}\")\n"
        "    elif op == 'valid_parentheses':\n"
        "        s = data[1] if len(data) > 1 else ''\n"
        "        print(valid_parentheses(s))\n"
        "    elif op == 'group_anagrams':\n"
        "        words = data[1].split() if len(data) > 1 else []\n"
        "        groups = group_anagrams(words)\n"
        "        # print as: group1|group2..., words comma-separated\n"
        "        out = ['.'.join(g) for g in groups]\n"
        "        print('|'.join(out))\n"
        "    elif op == 'merge_intervals':\n"
        "        # line: a,b a,b ...\n"
        "        items = data[1].split() if len(data) > 1 else []\n"
        "        intervals = []\n"
        "        for it in items:\n"
        "            a, b = it.split(',')\n"
        "            intervals.append([int(a), int(b)])\n"
        "        res = merge_intervals(intervals)\n"
        "        print(' '.join([f\"{a},{b}\" for a,b in res]))\n"
        "    elif op == 'coin_change':\n"
        "        coins = [int(x) for x in data[1].split()] if len(data) > 1 else []\n"
        "        amount = int(data[2]) if len(data) > 2 else 0\n"
        "        print(coin_change(coins, amount))\n"
        "    else:\n"
        "        print('unknown_op')\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )


def _javascript_solution_bundle() -> str:
    return (
        "const fs = require('fs');\n"
        "const input = fs.readFileSync(0, 'utf8').split(/\\r?\\n/);\n"
        "\n"
        "function reverseString(s){\n"
        "  return s.split('').reverse().join('');\n"
        "}\n"
        "\n"
        "function isPalindrome(s){\n"
        "  const t = (s || '').toLowerCase().replace(/[^a-z0-9]/g,'');\n"
        "  const r = t.split('').reverse().join('');\n"
        "  return (t === r) ? 'true' : 'false';\n"
        "}\n"
        "\n"
        "function twoSum(nums, target){\n"
        "  const seen = new Map();\n"
        "  for (let i=0;i<nums.length;i++){\n"
        "    const x = nums[i];\n"
        "    const need = target - x;\n"
        "    if (seen.has(need)) return [seen.get(need), i];\n"
        "    seen.set(x, i);\n"
        "  }\n"
        "  return [-1, -1];\n"
        "}\n"
        "\n"
        "function validParentheses(s){\n"
        "  const st = [];\n"
        "  const m = new Map([[')', '('], [']', '['], ['}', '{']]);\n"
        "  for (const ch of s){\n"
        "    if (ch==='('||ch==='['||ch==='{') st.push(ch);\n"
        "    else if (m.has(ch)){\n"
        "      if (st.length===0 || st[st.length-1]!==m.get(ch)) return 'false';\n"
        "      st.pop();\n"
        "    }\n"
        "  }\n"
        "  return st.length===0 ? 'true' : 'false';\n"
        "}\n"
        "\n"
        "function groupAnagrams(words){\n"
        "  const mp = new Map();\n"
        "  for (const w of words){\n"
        "    const key = w.split('').sort().join('');\n"
        "    if (!mp.has(key)) mp.set(key, []);\n"
        "    mp.get(key).push(w);\n"
        "  }\n"
        "  const groups = Array.from(mp.values()).map(g => g.slice().sort());\n"
        "  groups.sort((a,b) => (a.length-b.length) || ((a[0]||'').localeCompare(b[0]||'')));\n"
        "  return groups;\n"
        "}\n"
        "\n"
        "function mergeIntervals(intervals){\n"
        "  intervals.sort((x,y)=> x[0]-y[0]);\n"
        "  const res = [];\n"
        "  for (const it of intervals){\n"
        "    const a = it[0], b = it[1];\n"
        "    if (res.length===0 || a > res[res.length-1][1]) res.push([a,b]);\n"
        "    else res[res.length-1][1] = Math.max(res[res.length-1][1], b);\n"
        "  }\n"
        "  return res;\n"
        "}\n"
        "\n"
        "function coinChange(coins, amount){\n"
        "  const INF = 1e9;\n"
        "  const dp = new Array(amount+1).fill(INF);\n"
        "  dp[0] = 0;\n"
        "  for (let a=1;a<=amount;a++){\n"
        "    let best = INF;\n"
        "    for (const c of coins){\n"
        "      if (a-c>=0) best = Math.min(best, dp[a-c] + 1);\n"
        "    }\n"
        "    dp[a] = best;\n"
        "  }\n"
        "  return dp[amount] >= INF ? -1 : dp[amount];\n"
        "}\n"
        "\n"
        "const op = (input[0]||'').trim();\n"
        "if (op === 'reverse'){\n"
        "  const s = input[1] || '';\n"
        "  console.log(reverseString(s));\n"
        "} else if (op === 'palindrome'){\n"
        "  const s = input[1] || '';\n"
        "  console.log(isPalindrome(s));\n"
        "} else if (op === 'two_sum'){\n"
        "  const nums = (input[1]||'').trim().split(/\\s+/).filter(Boolean).map(x=>parseInt(x,10));\n"
        "  const target = parseInt((input[2]||'0').trim(),10);\n"
        "  const ans = twoSum(nums, target);\n"
        "  console.log(String(ans[0]) + ' ' + String(ans[1]));\n"
        "} else if (op === 'valid_parentheses'){\n"
        "  const s = input[1] || '';\n"
        "  console.log(validParentheses(s));\n"
        "} else if (op === 'group_anagrams'){\n"
        "  const words = (input[1]||'').trim().split(/\\s+/).filter(Boolean);\n"
        "  const groups = groupAnagrams(words);\n"
        "  const out = groups.map(g => g.join('.'));\n"
        "  console.log(out.join('|'));\n"
        "} else if (op === 'merge_intervals'){\n"
        "  const items = (input[1]||'').trim().split(/\\s+/).filter(Boolean);\n"
        "  const intervals = items.map(it => it.split(',').map(x=>parseInt(x,10)));\n"
        "  const res = mergeIntervals(intervals);\n"
        "  console.log(res.map(p => String(p[0]) + ',' + String(p[1])).join(' '));\n"
        "} else if (op === 'coin_change'){\n"
        "  const coins = (input[1]||'').trim().split(/\\s+/).filter(Boolean).map(x=>parseInt(x,10));\n"
        "  const amount = parseInt((input[2]||'0').trim(),10);\n"
        "  console.log(String(coinChange(coins, amount)));\n"
        "} else {\n"
        "  console.log('unknown_op');\n"
        "}\n"
    )


def _testcases() -> List[Tuple[str, str, str]]:
    # (op, stdin, expected_stdout)
    return [
        ("reverse", "reverse\nhello\n", "olleh\n"),
        ("reverse", "reverse\nracecar\n", "racecar\n"),
        ("palindrome", "palindrome\nA man, a plan, a canal: Panama\n", "true\n"),
        ("palindrome", "palindrome\nnot a palindrome\n", "false\n"),
        ("two_sum", "two_sum\n2 7 11 15\n9\n", "0 1\n"),
        ("two_sum", "two_sum\n3 2 4\n6\n", "1 2\n"),
        ("valid_parentheses", "valid_parentheses\n()[]{}\n", "true\n"),
        ("valid_parentheses", "valid_parentheses\n(]\n", "false\n"),
        ("group_anagrams", "group_anagrams\neat tea tan ate nat bat\n", "bat|nat.tan|ate.eat.tea\n"),
        ("merge_intervals", "merge_intervals\n1,3 2,6 8,10 15,18\n", "1,6 8,10 15,18\n"),
        ("coin_change", "coin_change\n1 2 5\n11\n", "3\n"),
        ("coin_change", "coin_change\n2\n3\n", "-1\n"),
    ]


def _run_case(
    client: PistonClient,
    mc: MetricsCollector,
    *,
    language: str,
    version: str,
    code: str,
    stdin: str,
    expected: str,
    case_name: str,
) -> bool:
    test_name = f"student_cases.test_student_algorithms.{language}.{case_name}"
    try:
        pr = client.execute(language, version, code, stdin=stdin, args=[])
        exit_code, stdout, stderr = _extract_run_fields(pr.data)
        ok = (exit_code == 0) and (stderr.strip() == "") and (stdout == expected)
        mc.record(
            test_name=test_name,
            language=language,
            status="pass" if ok else "fail",
            latency_ms=pr.latency_ms,
            error_type="" if ok else "wrong_output_or_exit",
            details={
                "exit_code": exit_code,
                "expected_stdout": expected,
                "stdout_preview": stdout[:2000],
                "stderr_preview": stderr[:2000],
            },
        )
        log.info("%s %s", "PASS" if ok else "FAIL", test_name)
        return ok
    except PistonAPIError as e:
        mc.record(
            test_name=test_name,
            language=language,
            status="fail",
            latency_ms=0.0,
            error_type=e.category,
            details={"error": str(e)},
        )
        log.error("FAIL %s (error_type=%s): %s", test_name, e.category, e)
        return False


def main() -> int:
    load_dotenv()
    base_url = os.getenv("PISTON_API_URL", "http://localhost:2000")
    client = PistonClient(base_url=base_url, api_key=os.getenv("PISTON_API_KEY", ""))
    mc = MetricsCollector()

    py_code = _python_solution_bundle()
    js_code = _javascript_solution_bundle()

    overall_ok = True
    cases = _testcases()

    for idx, (_op, stdin, expected) in enumerate(cases):
        overall_ok = _run_case(
            client,
            mc,
            language="python",
            version="3.10.0",
            code=py_code,
            stdin=stdin,
            expected=expected,
            case_name=f"case_{idx}",
        ) and overall_ok

        overall_ok = _run_case(
            client,
            mc,
            language="javascript",
            version="18.15.0",
            code=js_code,
            stdin=stdin,
            expected=expected,
            case_name=f"case_{idx}",
        ) and overall_ok

    results = mc.export()
    out_path = write_results_json("student_cases_test_student_algorithms.json", results)
    log.info("Wrote results: %s", out_path)
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

