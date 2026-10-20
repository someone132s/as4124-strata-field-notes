#!/usr/bin/env python3
"""Probe Strata conversation-cache reuse on an existing running configuration."""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
URL = "http://10.2.21.4:8080"
CASES = {
    "32K": (2, 3),
    "128K": (6, 7),
}


def get_json(path, timeout=20):
    with urllib.request.urlopen(URL + path, timeout=timeout) as response:
        return json.load(response)


def wait_idle(timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        metrics = get_json("/metrics")
        live = metrics.get("live") or {}
        if live.get("state") == "idle" and not live.get("queued"):
            return metrics
        time.sleep(1)
    raise TimeoutError("Strata did not become idle")


def request(body, marker):
    payload = json.loads(json.dumps(body))
    content = payload["messages"][0]["content"]
    payload["messages"][0]["content"] = f"[{marker}] " + content
    payload["max_tokens"] = 16
    payload["stream"] = False
    before = wait_idle()
    known = {row.get("time") for row in before.get("requests", [])}
    started = time.monotonic()
    request_object = urllib.request.Request(
        URL + "/v1/chat/completions",
        json.dumps(payload, ensure_ascii=False).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request_object, timeout=1200) as response:
        result = json.load(response)
    ended = time.monotonic()
    deadline = time.monotonic() + 90
    backend = None
    after = None
    while time.monotonic() < deadline:
        after = get_json("/metrics")
        fresh = [row for row in after.get("requests", []) if row.get("time") not in known]
        if fresh and (after.get("live") or {}).get("state") == "idle":
            backend = fresh[-1]
            break
        time.sleep(1)
    if backend is None or after is None:
        raise RuntimeError("request metrics not found")
    return {
        "started": started,
        "wall_s": ended - started,
        "usage": result.get("usage"),
        "backend": backend,
        "conversation_cache": after.get("conversation_cache"),
        "mem_available_mib": (after.get("hardware") or {}).get("ram_available_mib"),
        "ram_used_bytes": (after.get("hardware") or {}).get("ram_used"),
        "ram_total_bytes": (after.get("hardware") or {}).get("ram_total"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--lengths", default="32K,128K")
    args = parser.parse_args()
    out = ROOT / "outputs/Strata-Hermes-nightly-20261020/cache" / args.name
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / "outputs/numa-affinity-sweep-20261019/requests.jsonl"
    bodies = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
    ]
    record = {
        "name": args.name,
        "started": datetime.datetime.now().astimezone().isoformat(),
        "initial_engine": get_json("/metrics")["engine"],
        "initial_conversation_cache": get_json("/metrics").get("conversation_cache"),
        "rounds": [],
    }
    try:
        for length in [item.strip() for item in args.lengths.split(",") if item.strip()]:
            indexes = CASES[length]
            sequence = [
                ("A", indexes[0], "A1"),
                ("B", indexes[1], "B1"),
                ("A", indexes[0], "A2"),
                ("B", indexes[1], "B2"),
            ]
            round_record = {"length": length, "requests": []}
            for side, index, label in sequence:
                print(f"CACHE_REQUEST {args.name} {length} {label}", flush=True)
                row = request(bodies[index], f"cache-{args.name}-{length}-{side}")
                backend = row["backend"]
                row["label"] = label
                row["side"] = side
                row["reused"] = backend.get("reused")
                row["prompt_total"] = backend.get("prompt_total")
                row["prompt_read"] = backend.get("prompt_read")
                row["prompt_ms"] = backend.get("prompt_ms")
                row["reuse_ratio"] = (
                    backend.get("reused", 0) / backend.get("prompt_total", 1)
                    if backend.get("prompt_total") else 0
                )
                round_record["requests"].append(row)
                print(
                    f"CACHE_RESULT {length} {label} reused={row['reused']} "
                    f"ratio={row['reuse_ratio']:.3f} wall={row['wall_s']:.1f}",
                    flush=True,
                )
            record["rounds"].append(round_record)
        record["final_conversation_cache"] = get_json("/metrics").get("conversation_cache")
        record["status"] = "passed"
    except BaseException as error:
        record["status"] = "failed"
        record["error"] = f"{type(error).__name__}: {error}"
    record["finished"] = datetime.datetime.now().astimezone().isoformat()
    (out / "results.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": record["status"], "name": args.name}))
    raise SystemExit(0 if record["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
