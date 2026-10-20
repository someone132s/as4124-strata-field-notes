#!/usr/bin/env python3
"""Run the frozen Strata/Hermes engineering acceptance suite.

This file runs on Hermes-1 as the hermes user. Hidden oracles exist only in
the controller directory and are never mounted into the agent workspace.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


MODEL = "huihui-qwen3.8-flash-next-abliterated-ud-iq4_xs"
STRATA_BASE = "http://10.2.21.4:8080/v1"
HERMES = "/home/hermes/.local/bin/hermes"
DOCKER_SOCKET = "unix:///run/user/1001/docker.sock"
IMAGE = "nousresearch/hermes-sandbox:desktop"
VARIANTS = (("a", 20261020), ("b", 20261021))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def hermes_config(workspace: Path) -> str:
    return f"""model:
  default: "{MODEL}"
  provider: "strata-nightly"
providers:
  strata-nightly:
    api: "{STRATA_BASE}"
    api_key: "dummy"
    transport: "openai_chat"
    discover_models: false
    models:
      {MODEL}:
        context_length: 262144
agent:
  max_turns: 12
  run_budget_seconds: 285
  reasoning_effort: "medium"
  verify_on_stop: false
  verbose: false
terminal:
  backend: "docker"
  cwd: "/workspace"
  timeout: 90
  lifetime_seconds: 300
  home_mode: "real"
  docker_image: "{IMAGE}"
  docker_image_pinned: true
  docker_mount_cwd_to_workspace: false
  docker_volumes:
    - "{workspace}:/workspace"
  docker_network: false
  docker_persist_across_processes: false
  docker_orphan_reaper: true
  container_cpu: 2
  container_memory: 4096
  container_disk: 2048
  container_persistent: false
compression:
  enabled: false
memory:
  memory_enabled: false
  user_profile_enabled: false
fallback_providers: []
plugins:
  enabled: []
  disabled: []
mcp_servers: {{}}
"""


def generate_t1(root: Path, seed: int):
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    rng = random.Random(seed)
    people = ["Ada", "Ben", "Cleo", "Dana", "Eli", "Faye"]
    regions = ["north", "south"]
    rows = []
    expected = {name: {"total_cents": 0, "paid_orders": 0, "refunds": 0} for name in people}
    order_number = 0
    for person in people:
        for _ in range(3):
            order_number += 1
            order_id = f"O{order_number:03d}"
            amount = rng.randrange(1000, 12000)
            region = rng.choice(regions)
            rows.append({
                "event_id": f"{order_id}-v1", "order_id": order_id,
                "customer": person, "region": region, "version": 1,
                "kind": "sale", "amount_cents": amount, "currency": "USD",
                "status": rng.choice(["paid", "paid", "cancelled"]),
                "refund_for": "",
            })
            if rng.random() < 0.55:
                rows.append({
                    "event_id": f"{order_id}-v2", "order_id": order_id,
                    "customer": person, "region": region, "version": 2,
                    "kind": "sale", "amount_cents": amount + rng.randrange(-250, 251),
                    "currency": "USD", "status": rng.choice(["paid", "paid", "cancelled"]),
                    "refund_for": "",
                })
    latest = {}
    for row in rows:
        key = row["order_id"]
        if key not in latest or row["version"] > latest[key]["version"]:
            latest[key] = row
    for row in list(latest.values()):
        if row["status"] == "paid" and rng.random() < 0.25:
            refund = rng.randrange(100, min(900, row["amount_cents"]) + 1)
            rows.append({
                "event_id": f"R-{row['order_id']}", "order_id": f"R-{row['order_id']}",
                "customer": row["customer"], "region": row["region"], "version": 1,
                "kind": "refund", "amount_cents": refund, "currency": "USD",
                "status": "posted", "refund_for": row["order_id"],
            })
    rng.shuffle(rows)
    with (workspace / "transactions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in [*latest.values(), *[r for r in rows if r["kind"] == "refund"]]:
        if row["kind"] == "sale":
            if row["status"] != "paid":
                continue
            expected[row["customer"]]["total_cents"] += row["amount_cents"]
            expected[row["customer"]]["paid_orders"] += 1
        elif row["status"] == "posted":
            expected[row["customer"]]["total_cents"] -= row["amount_cents"]
            expected[row["customer"]]["refunds"] += 1
    oracle = {
        "currency": "USD",
        "customers": [
            {"customer": name, **values} for name, values in sorted(expected.items())
        ],
    }
    prompt = """Working directory: /workspace

Read transactions.csv. For each order_id, retain only the row with the highest version, independently of row order. From those retained rows:
- a sale with status paid adds amount_cents and one paid order;
- a sale with status cancelled adds nothing;
- a refund with status posted subtracts amount_cents and adds one refund.

Currencies are all USD. Write result.json containing exactly:
{"currency":"USD","customers":[{"customer":"name","total_cents":integer,"paid_orders":integer,"refunds":integer}, ...]}
Sort customers by name. Use integer cents, do not write text outside result.json as the answer artifact. Verify your file, then answer briefly.
"""
    write_text(root / "prompt.txt", prompt)
    return oracle


def generate_t2(root: Path, seed: int):
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    rng = random.Random(seed)
    db = workspace / "sales.db"
    connection = sqlite3.connect(db)
    connection.executescript(
        "CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT);"
        "CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER,paid_at TEXT,status TEXT);"
        "CREATE TABLE payments(order_id INTEGER,amount_cents INTEGER);"
    )
    names = ["Aster", "Brook", "Cedar", "Dune", "Elm", "Fern", "Grove", "Harbor"]
    for index, name in enumerate(names, 1):
        connection.execute("INSERT INTO customers VALUES(?,?)", (index, name))
    order_id = 0
    for customer_id in range(1, len(names) + 1):
        for _ in range(5):
            order_id += 1
            month = rng.choice(["2026-08", "2026-09", "2026-10"])
            day = rng.randrange(1, 28)
            paid_at = f"{month}-{day:02d}T12:00:00Z"
            status = rng.choice(["paid", "paid", "cancelled"])
            connection.execute("INSERT INTO orders VALUES(?,?,?,?)",
                               (order_id, customer_id, paid_at, status))
            connection.execute("INSERT INTO payments VALUES(?,?)",
                               (order_id, rng.randrange(1200, 25000)))
    connection.executescript(
        "INSERT INTO orders VALUES(999,1,'2026-09-30T23:59:59Z','paid');"
        "INSERT INTO payments VALUES(999,4444);"
        "INSERT INTO orders VALUES(1000,2,'2026-10-01T00:00:00Z','paid');"
        "INSERT INTO payments VALUES(1000,999999);"
    )
    expected_rows = connection.execute(
        """SELECT c.id,c.name,SUM(p.amount_cents) AS total
           FROM customers c JOIN orders o ON o.customer_id=c.id
           JOIN payments p ON p.order_id=o.id
           WHERE o.status='paid'
             AND o.paid_at >= '2026-09-01T00:00:00Z'
             AND o.paid_at < '2026-10-01T00:00:00Z'
           GROUP BY c.id,c.name
           ORDER BY total DESC,c.id ASC"""
    ).fetchall()
    connection.close()
    rows = []
    for rank, (customer_id, name, total) in enumerate(expected_rows, 1):
        rows.append({"customer_id": customer_id, "customer": name,
                     "total_cents": total, "rank": rank})
    oracle = {"window": "[2026-09-01T00:00:00Z,2026-10-01T00:00:00Z)", "rows": rows}
    prompt = """Working directory: /workspace

Use Python's sqlite3 and read sales.db read-only. Join customers, orders and payments.
Include an order only when status is paid and paid_at is >= 2026-09-01T00:00:00Z and
strictly < 2026-10-01T00:00:00Z. Group by customer, sum payments.amount_cents, and assign
rank 1,2,3,... after sorting by total_cents descending and customer id ascending.

Write result.json containing exactly:
{"window":"[2026-09-01T00:00:00Z,2026-10-01T00:00:00Z)","rows":[{"customer_id":int,"customer":str,"total_cents":int,"rank":int},...]}
Do not modify sales.db. Answer briefly after writing the file.
"""
    write_text(root / "prompt.txt", prompt)
    return oracle


INTERVALS_INITIAL = '''"""Closed integer interval utilities."""


def merge_intervals(intervals):
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: item[0])
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start < last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return [tuple(item) for item in merged]
'''


INTERVALS_TESTS = '''import json
import sys
sys.path.insert(0, "/workspace")
from intervals import merge_intervals

CASES = [
    ([], []),
    ([(5, 7)], [(5, 7)]),
    ([(1, 3), (3, 5)], [(1, 5)]),
    ([(1, 2), (2, 2)], [(1, 2)]),
    ([(1, 10), (2, 3)], [(1, 10)]),
    ([(8, 9), (1, 4), (4, 6)], [(1, 6), (8, 9)]),
    ([(1, 2), (4, 5), (2, 4)], [(1, 5)]),
    ([(0, 0), (1, 1)], [(0, 0), (1, 1)]),
    ([(-5, -2), (-2, 0), (2, 3)], [(-5, 0), (2, 3)]),
    ([(10, 12), (1, 3), (11, 13)], [(1, 3), (10, 13)]),
    ([(1, 3), (1, 3)], [(1, 3)]),
    ([(1, 5), (6, 8)], [(1, 5), (6, 8)]),
    ([(1, 4), (2, 8), (7, 9)], [(1, 9)]),
    ([(-1, 1), (0, 2), (3, 4)], [(-1, 2), (3, 4)]),
    ([(100, 101), (0, 1), (1, 2)], [(0, 2), (100, 101)]),
    ([(1, 2), (5, 6), (3, 4)], [(1, 2), (3, 4), (5, 6)]),
    ([(2, 2), (3, 3), (1, 4)], [(1, 4)]),
    ([(7, 8), (2, 3), (4, 7)], [(2, 3), (4, 8)]),
    ([(0, 10), (20, 30), (10, 20)], [(0, 30)]),
    ([(1, 2), (4, 5)], [(1, 2), (4, 5)]),
]
for args, expected in CASES:
    got = merge_intervals(args)
    if got != expected:
        raise AssertionError((args, expected, got))
for bad in [(2, 1), [(1, 3), (5, 4)], [("x", 2)]]:
    try:
        merge_intervals(bad)
    except (ValueError, TypeError):
        pass
    else:
        raise AssertionError(("invalid input accepted", bad))
print(json.dumps({"passed": len(CASES) + 3}))
'''


def generate_t3(root: Path, seed: int):
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    write_text(workspace / "intervals.py", INTERVALS_INITIAL)
    write_text(workspace / "public_test.py", '''from intervals import merge_intervals
assert merge_intervals([]) == []
assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]
assert merge_intervals([(1, 10), (2, 3)]) == [(1, 10)]
print("public tests passed")
''')
    prompt = """Working directory: /workspace

Edit only intervals.py. Implement merge_intervals(intervals) so it:
1. returns a new list of closed integer intervals merged when they overlap OR
   share an endpoint. "Touch" here means a shared endpoint only; adjacent ranges
   such as (0, 0) and (1, 1) remain separate;
2. sorts the result by start;
3. preserves duplicate input rows correctly;
4. raises ValueError for a pair whose start is greater than its end, and raises
   TypeError for a pair that does not contain exactly two integer bounds;
5. does not mutate the input.

You may run public_test.py. Do not rely on any network. After verification, answer briefly.
"""
    write_text(root / "prompt.txt", prompt)
    return {"passed": 23}


def generate_t4(root: Path, seed: int):
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    rng = random.Random(seed)
    service = f"catalog-{rng.randrange(100, 999)}"
    host = "10.40.0.7"
    port = rng.randrange(9000, 9999)
    features = ["metrics", "tracing", "metrics", "auth", "tracing"]
    old = {
        "service": service,
        "listen": f"{host}:{port}",
        "enabled": True,
        "features": features,
        "limits": {"max_connections": "256", "timeout_seconds": "45"},
        "owner": "platform",
        "release": {"channel": "stable", "build": rng.randrange(100, 999)},
        "legacy_note": "preserve me",
    }
    dump(workspace / "config-old.json", old)
    extras = {key: old[key] for key in ("owner", "release", "legacy_note")}
    oracle = {
        "service": {"name": service, "host": host, "port": port, "enabled": True},
        "features": ["auth", "metrics", "tracing"],
        "limits": {"max_connections": 256, "timeout_seconds": 45},
        "extra": extras,
    }
    prompt = """Working directory: /workspace

Migrate config-old.json to the v2 shape and write result.json:
- service.listen "HOST:PORT" becomes service.host, integer service.port,
  service.name from old service, and service.enabled;
- features become a sorted, case-sensitive set (duplicates removed);
- limits.max_connections and limits.timeout_seconds become integers;
- every top-level key not named service, listen, enabled, features, or limits
  must be preserved unchanged under extra.

The expected top-level keys are service, features, limits, extra. Do not modify
config-old.json. Write valid JSON and answer briefly.
"""
    write_text(root / "prompt.txt", prompt)
    return oracle


def generate_t5(root: Path, seed: int):
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    rng = random.Random(seed)
    request_id = f"req-{rng.randrange(100000, 999999)}"
    stamp = f"2026-10-{rng.randrange(10, 20):02d}T08:1{rng.randrange(0, 9)}:00Z"
    files = {
        "edge.log": f"{stamp} INFO edge {request_id} accepted route=/checkout attempt=1\n",
        "payments.log": (
            f"{stamp} WARN payments {request_id} upstream=acquirer code=ERR_PAYMENT_503 retryable=true\n"
            f"{stamp} INFO payments {request_id} action=propagate_to_orders\n"
        ),
        "orders.log": (
            f"{stamp} ERROR orders {request_id} received=ERR_PAYMENT_503 caused_by=payments\n"
            f"{stamp} INFO orders {request_id} action=propagate_to_gateway\n"
        ),
        "gateway.log": (
            f"{stamp} ERROR gateway {request_id} received=ERR_ORDER_BLOCKED caused_by=orders\n"
            f"{stamp} INFO gateway {request_id} user_response=422\n"
        ),
    }
    for name, text in files.items():
        write_text(workspace / name, text)
    oracle = {
        "request_id": request_id,
        "first_failure_component": "payments",
        "first_failure_code": "ERR_PAYMENT_503",
        "chain": [
            {"from": "payments", "to": "orders"},
            {"from": "orders", "to": "gateway"},
        ],
        "user_response": 422,
    }
    prompt = f"""Working directory: /workspace

Investigate request {request_id} across edge.log, payments.log, orders.log and gateway.log.
Find the component where failure originates and the propagation chain. A downstream
component receiving an error is not the origin. The chain must begin at
first_failure_component and contain only downstream failure propagation after the
original error. Include edges only between payments, orders and gateway; stop at
gateway. Do not include the normal edge request or an edge to the user.
Write result.json containing exactly:
{{"request_id":str,"first_failure_component":str,"first_failure_code":str,
"chain":[{{"from":str,"to":str}},...],"user_response":int}}
Use component names without the .log suffix. Answer briefly after writing the file.
"""
    write_text(root / "prompt.txt", prompt)
    return oracle


def generate_t6(root: Path, seed: int):
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    rng = random.Random(seed)
    stock = {"A-100": 12, "B-200": 7, "C-300": 20}
    names = {"A-100": "Anvil", "B-200": "Bolt", "C-300": "Clamp"}
    with (workspace / "seed.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sku", "name", "qty", "updated_at"])
        for sku, qty in stock.items():
            writer.writerow([sku, names[sku], qty, "2026-10-01T00:00:00Z"])
    changes = [
        {"sku": "A-100", "delta": -4},
        {"sku": "B-200", "delta": 8},
        {"sku": "C-300", "delta": -6},
    ]
    dump(workspace / "changes2.json", changes)
    correction = {"sku": "C-300", "set_qty": 11}
    dump(workspace / "correction3.json", correction)
    for change in changes:
        stock[change["sku"]] += change["delta"]
    stock[correction["sku"]] = correction["set_qty"]
    oracle = {
        "rows": [
            {"sku": sku, "name": names[sku], "qty": stock[sku]} for sku in sorted(stock)
        ]
    }
    prompts = [
        """Working directory: /workspace

Turn 1 of 3. Create inventory.db with SQLite table inventory(sku TEXT PRIMARY KEY,
name TEXT NOT NULL, qty INTEGER NOT NULL, updated_at TEXT NOT NULL). Load exactly
the rows in seed.csv. Write turn1.json as {"rows":3}. Do not use any other data
source. Answer briefly.
""",
        """Turn 2 of 3. Read changes2.json and apply each delta to the current inventory.qty
in file order. No quantity may become negative. Preserve sku and name. Write
turn2.json as a sorted JSON list with fields sku,name,qty. Answer briefly.
""",
        """Turn 3 of 3. Read correction3.json and set that SKU's qty to set_qty. Write
inventory.json as a JSON list sorted by sku, containing exactly sku,name,qty.
Do not recreate the database or use seed.csv again. Answer briefly.
""",
    ]
    for index, prompt in enumerate(prompts, 1):
        write_text(root / f"prompt{index}.txt", prompt)
    return oracle


GENERATORS = {
    "T1": generate_t1,
    "T2": generate_t2,
    "T3": generate_t3,
    "T4": generate_t4,
    "T5": generate_t5,
    "T6": generate_t6,
}


def run_command(command: list[str], cwd: Path, timeout: int, env=None):
    started = time.monotonic()
    try:
        result = subprocess.run(
            command, cwd=cwd, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return result.returncode, result.stdout, time.monotonic() - started
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        return 124, output, time.monotonic() - started


def hermes_call(case_root: Path, prompt_path: Path, timeout: int, resume="") -> dict:
    home = case_root / "home"
    workspace = case_root / "workspace"
    home.mkdir(parents=True, exist_ok=True)
    write_text(home / "config.yaml", hermes_config(workspace))
    env = os.environ.copy()
    env.update({
        "HERMES_HOME": str(home),
        "HOME": "/home/hermes",
        "XDG_RUNTIME_DIR": "/run/user/1001",
        "DOCKER_HOST": DOCKER_SOCKET,
    })
    command = [
        HERMES, "chat", "--oneshot", "--query-file", str(prompt_path),
        "--in", str(workspace), "--toolsets", "terminal,file",
        "--ignore-rules", "--yolo", "--format", "stream-json",
        "--max-turns", "12",
    ]
    if resume:
        command.extend(["--resume", resume])
    code, output, duration = run_command(command, case_root, timeout, env)
    write_text(case_root / f"hermes-{time.time_ns()}.jsonl", output)
    session_id = ""
    result_event = None
    tool_calls = 0
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "tool_use":
            tool_calls += 1
        if event.get("type") == "result":
            result_event = event
            session_id = event.get("session_id") or session_id
    if not result_event:
        for line in output.splitlines():
            if line.startswith("Session: "):
                session_id = line.split(": ", 1)[1].strip()
    return {
        "returncode": code,
        "duration_s": duration,
        "session_id": session_id,
        "tool_calls": tool_calls,
        "result": result_event,
        "output_tail": output[-5000:],
    }


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def grade(task: str, case_root: Path, oracle) -> dict:
    workspace = case_root / "workspace"
    try:
        if task == "T1":
            actual = read_json(workspace / "result.json")
            return {"passed": actual == oracle, "actual": actual}
        if task == "T2":
            actual = read_json(workspace / "result.json")
            return {"passed": actual == oracle, "actual": actual}
        if task == "T3":
            hidden = case_root / "oracle"
            hidden.mkdir(exist_ok=True)
            write_text(hidden / "test_intervals.py", INTERVALS_TESTS)
            hidden.chmod(0o700)
            command = [
                "docker", "run", "--rm", "--network=none",
                "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "-v", f"{workspace}:/workspace:ro",
                "-v", f"{hidden}:/oracle:ro",
                IMAGE, "python", "/oracle/test_intervals.py",
            ]
            code, output, _ = run_command(command, case_root, 60, os.environ.copy())
            return {"passed": code == 0, "validator_output": output[-4000:]}
        if task == "T4":
            actual = read_json(workspace / "result.json")
            return {"passed": actual == oracle, "actual": actual}
        if task == "T5":
            actual = read_json(workspace / "result.json")
            return {"passed": actual == oracle, "actual": actual}
        if task == "T6":
            actual = read_json(workspace / "inventory.json")
            db = workspace / "inventory.db"
            db_ok = False
            if db.exists():
                try:
                    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                    db_rows = connection.execute(
                        "SELECT sku,name,qty FROM inventory ORDER BY sku"
                    ).fetchall()
                    connection.close()
                    db_ok = [{"sku": s, "name": n, "qty": q}
                             for s, n, q in db_rows] == oracle["rows"]
                except Exception:
                    db_ok = False
            return {"passed": actual == oracle["rows"] and db_ok,
                    "actual": actual, "expected": oracle["rows"],
                    "database_matches": db_ok}
        raise ValueError(task)
    except Exception as error:
        return {"passed": False, "error": f"{type(error).__name__}: {error}"}


def run_case(task: str, variant: str, seed: int, run_root: Path) -> dict:
    case_root = run_root / "cases" / f"{task}-{variant}"
    if case_root.exists():
        shutil.rmtree(case_root)
    case_root.mkdir(parents=True)
    oracle = GENERATORS[task](case_root, seed)
    workspace = case_root / "workspace"
    initial_hashes = {
        str(path.relative_to(workspace)): sha256(path)
        for path in workspace.rglob("*") if path.is_file()
    }
    calls = []
    if task == "T6":
        session = ""
        elapsed = 0.0
        for index in range(1, 4):
            remaining = max(30, int(300 - elapsed))
            call = hermes_call(case_root, case_root / f"prompt{index}.txt", remaining, session)
            calls.append(call)
            elapsed += call["duration_s"]
            session = call.get("session_id") or session
            if call["returncode"] != 0 or not session:
                break
    else:
        calls.append(hermes_call(case_root, case_root / "prompt.txt", 300))
    mutation = [
        name for name, digest in initial_hashes.items()
        if name not in {"intervals.py"} and (
            not (workspace / name).exists() or sha256(workspace / name) != digest
        )
    ]
    grade_result = grade(task, case_root, oracle)
    result = {
        "case": f"{task}-{variant}",
        "task": task,
        "variant": variant,
        "seed": seed,
        "passed": bool(grade_result.get("passed")) and not mutation,
        "duration_s": sum(call["duration_s"] for call in calls),
        "tool_calls": sum(call["tool_calls"] for call in calls),
        "calls": calls,
        "grade": grade_result,
        "forbidden_input_mutations": mutation,
        "session_preserved": (
            len({call.get("session_id") for call in calls}) == 1
            if task == "T6" else None
        ),
    }
    dump(case_root / "case-result.json", result)
    return result


def selftest(run_root: Path) -> dict:
    check = run_root / "selftest"
    check.mkdir(parents=True, exist_ok=True)
    good = {"x": 1}
    dump(check / "good.json", good)
    dump(check / "bad.json", {"x": 2})
    ok = read_json(check / "good.json") == good
    rejected = read_json(check / "bad.json") != good
    hidden = check / "oracle"
    hidden.mkdir(exist_ok=True)
    write_text(hidden / "test_intervals.py", INTERVALS_TESTS)
    broken_ws = check / "broken"
    fixed_ws = check / "fixed"
    broken_ws.mkdir(exist_ok=True)
    fixed_ws.mkdir(exist_ok=True)
    write_text(broken_ws / "intervals.py", INTERVALS_INITIAL)
    write_text(fixed_ws / "intervals.py", '''def merge_intervals(intervals):
    result = []
    for item in intervals:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise TypeError("expected pair")
        start, end = item
        if not isinstance(start, int) or not isinstance(end, int):
            raise TypeError("expected integer bounds")
        if start > end:
            raise ValueError("start > end")
        result.append([start, end])
    result.sort()
    merged = []
    for start, end in result:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [tuple(pair) for pair in merged]
''')
    def code_test(workspace):
        command = [
            "docker", "run", "--rm", "--network=none",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "-v", f"{workspace}:/workspace:ro", "-v", f"{hidden}:/oracle:ro",
            IMAGE, "python", "/oracle/test_intervals.py",
        ]
        return run_command(command, check, 60, os.environ.copy())[0]
    broken_code = code_test(broken_ws)
    fixed_code = code_test(fixed_ws)
    result = {
        "json_accepts_correct": ok,
        "json_rejects_wrong": rejected,
        "validator_rejects_buggy": broken_code != 0,
        "validator_accepts_fixed": fixed_code == 0,
    }
    result["passed"] = all(result.values())
    dump(run_root / "selftest.json", result)
    return result


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: nightly_suite.py RUN_ROOT [--selftest]")
    run_root = Path(sys.argv[1]).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    if "--selftest" in sys.argv:
        result = selftest(run_root)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result["passed"] else 1)
    only = None
    if "--only" in sys.argv:
        only = {
            item.strip().upper()
            for item in sys.argv[sys.argv.index("--only") + 1].split(",")
            if item.strip()
        }
    suite = []
    started = time.time()
    for task in GENERATORS:
        if only is not None and task not in only:
            continue
        for variant, seed in VARIANTS:
            print(f"CASE_START {task}-{variant}", flush=True)
            try:
                result = run_case(task, variant, seed, run_root)
            except Exception as error:
                result = {
                    "case": f"{task}-{variant}", "task": task, "variant": variant,
                    "seed": seed, "passed": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            suite.append(result)
            dump(run_root / "results.partial.json", suite)
            print(
                f"CASE_DONE {result['case']} passed={result['passed']} "
                f"duration={result.get('duration_s', 0):.1f}s "
                f"tools={result.get('tool_calls', 0)}",
                flush=True,
            )
    summary = {
        "suite": "strata-hermes-engineering-v3",
        "model": MODEL,
        "started": started,
        "finished": time.time(),
        "passed": sum(1 for item in suite if item.get("passed")),
        "total": len(suite),
        "cases": suite,
    }
    dump(run_root / "results.json", summary)
    print(json.dumps({"passed": summary["passed"], "total": summary["total"]}), flush=True)
    raise SystemExit(0 if summary["passed"] >= 11 else 2)


if __name__ == "__main__":
    main()
