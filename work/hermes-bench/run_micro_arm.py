#!/usr/bin/env python3
"""Apply one Strata config, restart it, and run a fixed four-case micro suite."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
REMOTE_CONFIG = "/opt/strata-data/config/strata-huihui-ud-iq4_xs-q8ple-vision-v0.1.45.json"
REMOTE_COMPOSE = "/opt/strata-deploy/compose.yaml"
URL = "http://10.2.21.4:8080"
MODEL = "huihui-qwen3.8-flash-next-abliterated-ud-iq4_xs"
SSH = [
    "ssh", "-i", "work/id_ed25519_pve_local", "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
    "-o", "UserKnownHostsFile=work/known_hosts_vm502", "root@10.2.21.4",
]
SCP = [
    "scp", "-i", "work/id_ed25519_pve_local", "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
    "-o", "UserKnownHostsFile=work/known_hosts_vm502",
]
CASES = [
    (0, "4K-simple"), (1, "4K-complex"),
    (2, "32K-simple"), (3, "32K-complex"),
]


def command(args, timeout=300):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(
            "command failed: " + " ".join(args) + "\n"
            + result.stdout[-3000:] + "\n" + result.stderr[-3000:]
        )
    return result.stdout


def remote(script, timeout=300):
    return command(SSH + [script], timeout)


def get_json(path, timeout=20):
    with urllib.request.urlopen(URL + path, timeout=timeout) as response:
        return json.load(response)


def set_arg(config, flag, value):
    args = list(config.get("args") or [])
    if flag in args:
        args[args.index(flag) + 1] = str(value)
    else:
        args.extend([flag, str(value)])
    config["args"] = args


def wait_ready(version="0.1.45", timeout=420):
    deadline = time.monotonic() + timeout
    errors = []
    while time.monotonic() < deadline:
        try:
            health = get_json("/health")
            metrics = get_json("/metrics")
            live = metrics.get("live") or {}
            if (
                health.get("status") == "ok" and health.get("loaded")
                and metrics.get("engine", {}).get("version") == version
                and live.get("state") == "idle"
            ):
                return health, metrics
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
        time.sleep(5)
    raise TimeoutError((errors or ["no health response"])[-1])


def restart():
    remote(
        "cd /opt/strata-deploy && docker compose -f compose.yaml "
        "up -d --no-deps --force-recreate strata",
        timeout=300,
    )
    return wait_ready()


def stream_case(body, marker):
    payload = json.loads(json.dumps(body))
    messages = payload["messages"]
    content = messages[0]["content"]
    if isinstance(content, str):
        messages[0]["content"] = f"[{marker}] " + content
    else:
        messages[0]["content"] = content
    payload["max_tokens"] = 512
    payload["stream"] = True
    payload["stream_options"] = {"include_usage": True}
    before = get_json("/metrics")
    if (before.get("live") or {}).get("state") != "idle":
        raise RuntimeError("Strata busy before request")
    known = {row.get("time") for row in before.get("requests", [])}
    raw = json.dumps(payload, ensure_ascii=False).encode()
    started = time.monotonic()
    first = None
    first_text = None
    usage = {}
    timings = {}
    finish = None
    done = False
    request = urllib.request.Request(
        URL + "/v1/chat/completions", raw,
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=1200) as response:
        for raw_line in response:
            line = raw_line.decode().strip()
            if not line.startswith("data:"):
                continue
            value = line[5:].strip()
            if value == "[DONE]":
                done = True
                break
            event = json.loads(value)
            if event.get("error"):
                raise RuntimeError(str(event["error"]))
            usage = event.get("usage") or usage
            timings = event.get("timings") or timings
            for choice in event.get("choices") or []:
                delta = choice.get("delta") or {}
                part = delta.get("content") or delta.get("reasoning_content") or ""
                if part:
                    now = time.monotonic()
                    first = first or now
                    if delta.get("content") and first_text is None:
                        first_text = now
                finish = choice.get("finish_reason") or finish
    ended = time.monotonic()
    if not done or first is None:
        raise RuntimeError("request stream ended without completion")
    deadline = time.monotonic() + 60
    backend = None
    while time.monotonic() < deadline:
        after = get_json("/metrics")
        fresh = [row for row in after.get("requests", []) if row.get("time") not in known]
        if fresh and (after.get("live") or {}).get("state") == "idle":
            backend = fresh[-1]
            break
        time.sleep(1)
    if backend is None:
        raise RuntimeError("request did not appear in /metrics")
    return {
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "stream_first_s": first - started,
        "first_text_s": (first_text - started) if first_text else None,
        "wall_s": ended - started,
        "usage": usage,
        "timings": timings,
        "backend": backend,
        "finish_reason": finish,
        "prefix_reused": backend.get("reused", 0),
    }


def warmup(body):
    payload = json.loads(json.dumps(body))
    payload["messages"][0]["content"] = "[micro-warmup] " + payload["messages"][0]["content"]
    payload["max_tokens"] = 64
    payload["stream"] = False
    request = urllib.request.Request(
        URL + "/v1/chat/completions",
        json.dumps(payload, ensure_ascii=False).encode(),
        {"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=1200) as response:
        json.load(response)
    wait_ready()
    return time.monotonic() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--set-arg", action="append", default=[])
    parser.add_argument("--set-env", action="append", default=[])
    parser.add_argument("--unset-env", action="append", default=[])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output-root", default="outputs/Strata-Hermes-nightly-20261020/micro")
    args = parser.parse_args()

    out = ROOT / args.output_root / args.name
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / args.base).read_text(encoding="utf-8"))
    for assignment in args.set_arg:
        flag, value = assignment.split("=", 1)
        set_arg(config, flag, value)
    env = dict(config.get("env") or {})
    for assignment in args.set_env:
        key, value = assignment.split("=", 1)
        env[key] = value
    for key in args.unset_env:
        env.pop(key, None)
    config["env"] = env
    candidate = out / "candidate-config.json"
    candidate.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    remote_tmp = f"/tmp/{args.name}-config.json"
    command(SCP + [str(candidate), f"root@10.2.21.4:{remote_tmp}"], timeout=60)
    remote(f"install -m 600 {shlex.quote(remote_tmp)} {REMOTE_CONFIG}")

    record = {
        "name": args.name,
        "started": datetime.datetime.now().astimezone().isoformat(),
        "base": args.base,
        "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "set_arg": args.set_arg,
        "set_env": args.set_env,
        "unset_env": args.unset_env,
        "config_before_health": get_json("/health"),
        "rows": [],
    }
    source = ROOT / "outputs/numa-affinity-sweep-20261019/requests.jsonl"
    bodies = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
    ]
    try:
        health, metrics = restart()
        record["health"] = health
        record["engine"] = metrics["engine"]
        record["process"] = remote(
            "ps -eo args | grep '^/opt/strata/engine/strata --serve'"
        ).strip()
        record["warmup_s"] = warmup(bodies[CASES[0][0]])
        for repeat in range(args.repeats):
            for index, label in CASES:
                marker = f"nightly-{args.name}-{repeat}-{label}"
                row = stream_case(bodies[index], marker)
                backend = row["backend"]
                row.update({
                    "label": label,
                    "repeat": repeat,
                    "prompt_tokens": backend.get("prompt_tokens"),
                    "output_tokens": backend.get("output_tokens"),
                    "prefill_tok_s": (
                        backend["prompt_tokens"] / (backend["prompt_ms"] / 1000)
                        if backend.get("prompt_ms") else None
                    ),
                    "decode_tok_s": backend.get("decode_tok_s"),
                    "prompt_ms": backend.get("prompt_ms"),
                    "decode_ms": backend.get("decode_ms"),
                    "draft_accept_rate": (
                        backend.get("drafts_accepted", 0) / backend.get("drafts_offered")
                        if backend.get("drafts_offered") else None
                    ),
                })
                record["rows"].append(row)
                print(
                    f"ROW {args.name} {label} repeat={repeat} "
                    f"prefill={row['prefill_tok_s']:.1f} "
                    f"decode={row['decode_tok_s']:.1f} "
                    f"wall={row['wall_s']:.1f}",
                    flush=True,
                )
        record["status"] = "passed"
    except BaseException as error:
        record["status"] = "failed"
        record["error"] = f"{type(error).__name__}: {error}"
    record["finished"] = datetime.datetime.now().astimezone().isoformat()
    (out / "results.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": record["status"], "name": args.name,
        "rows": len(record["rows"]), "error": record.get("error"),
    }, ensure_ascii=False))
    raise SystemExit(0 if record["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
