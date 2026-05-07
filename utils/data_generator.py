from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CodePayload:
    name: str
    language: str
    version: str
    code: str
    stdin: str = ""
    expected_stdout: Optional[str] = None


def python_hello_world() -> CodePayload:
    return CodePayload(
        name="hello_world",
        language="python",
        version="3.10.0",
        code='print("HELLO_FROM_PYTHON")\n',
        expected_stdout="HELLO_FROM_PYTHON\n",
    )


def javascript_hello_world() -> CodePayload:
    return CodePayload(
        name="hello_world",
        language="javascript",
        version="18.15.0",
        code='console.log("HELLO_FROM_JAVASCRIPT");\n',
        expected_stdout="HELLO_FROM_JAVASCRIPT\n",
    )


def python_stdin_echo() -> CodePayload:
    code = (
        "import sys\n"
        "data = sys.stdin.read()\n"
        "sys.stdout.write(data)\n"
    )
    stdin = "line1\nline2\nline3\n"
    return CodePayload(
        name="stdin_echo",
        language="python",
        version="3.10.0",
        code=code,
        stdin=stdin,
        expected_stdout=stdin,
    )


def javascript_stdin_echo() -> CodePayload:
    code = (
        "process.stdin.setEncoding('utf8');\n"
        "let data = '';\n"
        "process.stdin.on('data', chunk => data += chunk);\n"
        "process.stdin.on('end', () => { process.stdout.write(data); });\n"
    )
    stdin = "line1\nline2\nline3\n"
    return CodePayload(
        name="stdin_echo",
        language="javascript",
        version="18.15.0",
        code=code,
        stdin=stdin,
        expected_stdout=stdin,
    )


def _fizzbuzz_expected(n: int) -> str:
    out: List[str] = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            out.append("FizzBuzz")
        elif i % 3 == 0:
            out.append("Fizz")
        elif i % 5 == 0:
            out.append("Buzz")
        else:
            out.append(str(i))
    return "\n".join(out) + "\n"


def python_fizzbuzz(n: int = 20) -> CodePayload:
    code = (
        "import sys\n"
        "n = int(sys.stdin.read().strip() or '0')\n"
        "for i in range(1, n+1):\n"
        "    if i % 15 == 0:\n"
        "        print('FizzBuzz')\n"
        "    elif i % 3 == 0:\n"
        "        print('Fizz')\n"
        "    elif i % 5 == 0:\n"
        "        print('Buzz')\n"
        "    else:\n"
        "        print(i)\n"
    )
    stdin = f"{n}\n"
    return CodePayload(
        name="fizzbuzz",
        language="python",
        version="3.10.0",
        code=code,
        stdin=stdin,
        expected_stdout=_fizzbuzz_expected(n),
    )


def javascript_fizzbuzz(n: int = 20) -> CodePayload:
    code = (
        "process.stdin.setEncoding('utf8');\n"
        "let input = '';\n"
        "process.stdin.on('data', c => input += c);\n"
        "process.stdin.on('end', () => {\n"
        "  const n = parseInt((input || '').trim() || '0', 10);\n"
        "  for (let i = 1; i <= n; i++) {\n"
        "    if (i % 15 === 0) console.log('FizzBuzz');\n"
        "    else if (i % 3 === 0) console.log('Fizz');\n"
        "    else if (i % 5 === 0) console.log('Buzz');\n"
        "    else console.log(String(i));\n"
        "  }\n"
        "});\n"
    )
    stdin = f"{n}\n"
    return CodePayload(
        name="fizzbuzz",
        language="javascript",
        version="18.15.0",
        code=code,
        stdin=stdin,
        expected_stdout=_fizzbuzz_expected(n),
    )


def python_fibonacci(n: int = 28) -> CodePayload:
    code = (
        "import sys\n"
        "sys.setrecursionlimit(10000)\n"
        "n = int(sys.stdin.read().strip() or '0')\n"
        "def fib(k):\n"
        "    return k if k < 2 else fib(k-1) + fib(k-2)\n"
        "print(fib(n))\n"
    )
    stdin = f"{n}\n"

    def fibv(k: int) -> int:
        return k if k < 2 else fibv(k - 1) + fibv(k - 2)

    return CodePayload(
        name="fibonacci",
        language="python",
        version="3.10.0",
        code=code,
        stdin=stdin,
        expected_stdout=f"{fibv(n)}\n",
    )


def javascript_fibonacci(n: int = 28) -> CodePayload:
    code = (
        "process.stdin.setEncoding('utf8');\n"
        "let input = '';\n"
        "process.stdin.on('data', c => input += c);\n"
        "process.stdin.on('end', () => {\n"
        "  const n = parseInt((input || '').trim() || '0', 10);\n"
        "  function fib(k) { return k < 2 ? k : fib(k-1) + fib(k-2); }\n"
        "  console.log(String(fib(n)));\n"
        "});\n"
    )
    stdin = f"{n}\n"

    def fibv(k: int) -> int:
        return k if k < 2 else fibv(k - 1) + fibv(k - 2)

    return CodePayload(
        name="fibonacci",
        language="javascript",
        version="18.15.0",
        code=code,
        stdin=stdin,
        expected_stdout=f"{fibv(n)}\n",
    )


def python_sort_array() -> CodePayload:
    code = (
        "import sys\n"
        "data = sys.stdin.read().strip().split()\n"
        "arr = [int(x) for x in data]\n"
        "arr.sort()\n"
        "print(' '.join(str(x) for x in arr))\n"
    )
    stdin = "9 1 5 3 7 2\n"
    expected = "1 2 3 5 7 9\n"
    return CodePayload(
        name="sort_array",
        language="python",
        version="3.10.0",
        code=code,
        stdin=stdin,
        expected_stdout=expected,
    )


def javascript_sort_array() -> CodePayload:
    code = (
        "process.stdin.setEncoding('utf8');\n"
        "let input = '';\n"
        "process.stdin.on('data', c => input += c);\n"
        "process.stdin.on('end', () => {\n"
        "  const arr = input.trim().split(/\\s+/).filter(Boolean).map(x => parseInt(x, 10));\n"
        "  arr.sort((a,b) => a-b);\n"
        "  console.log(arr.map(String).join(' '));\n"
        "});\n"
    )
    stdin = "9 1 5 3 7 2\n"
    expected = "1 2 3 5 7 9\n"
    return CodePayload(
        name="sort_array",
        language="javascript",
        version="18.15.0",
        code=code,
        stdin=stdin,
        expected_stdout=expected,
    )


def python_matrix_multiply() -> CodePayload:
    code = (
        "import sys\n"
        "vals = [int(x) for x in sys.stdin.read().strip().split()]\n"
        "a = [vals[i*3:(i+1)*3] for i in range(3)]\n"
        "b = [vals[9+i*3:9+(i+1)*3] for i in range(3)]\n"
        "c = [[0]*3 for _ in range(3)]\n"
        "for i in range(3):\n"
        "    for j in range(3):\n"
        "        s = 0\n"
        "        for k in range(3):\n"
        "            s += a[i][k] * b[k][j]\n"
        "        c[i][j] = s\n"
        "for row in c:\n"
        "    print(' '.join(str(x) for x in row))\n"
    )
    stdin = "1 2 3 4 5 6 7 8 9  9 8 7 6 5 4 3 2 1\n"
    expected = "30 24 18\n84 69 54\n138 114 90\n"
    return CodePayload(
        name="matrix_multiply",
        language="python",
        version="3.10.0",
        code=code,
        stdin=stdin,
        expected_stdout=expected,
    )


def javascript_matrix_multiply() -> CodePayload:
    code = (
        "process.stdin.setEncoding('utf8');\n"
        "let input = '';\n"
        "process.stdin.on('data', c => input += c);\n"
        "process.stdin.on('end', () => {\n"
        "  const vals = input.trim().split(/\\s+/).filter(Boolean).map(x => parseInt(x, 10));\n"
        "  const a = [vals.slice(0,3), vals.slice(3,6), vals.slice(6,9)];\n"
        "  const b = [vals.slice(9,12), vals.slice(12,15), vals.slice(15,18)];\n"
        "  const c = [[0,0,0],[0,0,0],[0,0,0]];\n"
        "  for (let i=0;i<3;i++){\n"
        "    for (let j=0;j<3;j++){\n"
        "      let s=0;\n"
        "      for (let k=0;k<3;k++) s += a[i][k]*b[k][j];\n"
        "      c[i][j]=s;\n"
        "    }\n"
        "  }\n"
        "  for (const row of c) console.log(row.map(String).join(' '));\n"
        "});\n"
    )
    stdin = "1 2 3 4 5 6 7 8 9  9 8 7 6 5 4 3 2 1\n"
    expected = "30 24 18\n84 69 54\n138 114 90\n"
    return CodePayload(
        name="matrix_multiply",
        language="javascript",
        version="18.15.0",
        code=code,
        stdin=stdin,
        expected_stdout=expected,
    )


def get_payloads() -> Dict[str, Dict[str, CodePayload]]:
    return {
        "python": {
            "hello_world": python_hello_world(),
            "stdin_echo": python_stdin_echo(),
            "fizzbuzz": python_fizzbuzz(),
            "fibonacci": python_fibonacci(),
            "sort_array": python_sort_array(),
            "matrix_multiply": python_matrix_multiply(),
        },
        "javascript": {
            "hello_world": javascript_hello_world(),
            "stdin_echo": javascript_stdin_echo(),
            "fizzbuzz": javascript_fizzbuzz(),
            "fibonacci": javascript_fibonacci(),
            "sort_array": javascript_sort_array(),
            "matrix_multiply": javascript_matrix_multiply(),
        },
    }


def pick_payload(language: str, name: str) -> CodePayload:
    payloads = get_payloads()
    if language not in payloads:
        raise KeyError(f"Unsupported language: {language}")
    if name not in payloads[language]:
        raise KeyError(f"Unknown payload name: {name}")
    return payloads[language][name]

