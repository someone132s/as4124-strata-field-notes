#!/usr/bin/env python3
"""Paired 250 W / 180 W measurement on the running Strata service."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
URL = "http://10.2.21.4:8080"
UUIDS = [
    "GPU-be897daa-b730-b812-cac5-0677e7c00d5b",
    "GPU-9a371e9d-99d5-eb30-e2f1-1a8cef3b6f03",
]
SSH = [
    "ssh", "-i", "work/id_ed25519_pve_local", "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
    "-o", "UserKnownHostsFile=work/known_hosts_vm502", "root@10.2.21.4",
]


def get_json(path, timeout=20):
    with urllib.request.urlopen(URL + path, timeout=timeout) as response:
        return json.load(response)


def set_power(watts):
    for uuid in UUIDS:
        result = subprocess.run(
            SSH + [f"nvidia-smi -i {uuid} -pl {watts}"],
            cwd=ROOT, text=True, capture_output=True, timeout=30,
        )
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
    time.sleep(5)
    return subprocess.run(
        SSH + ["nvidia-smi --query-gpu=uuid,power.limit,power.draw,temperature.gpu "
               "--format=csv,noheader"],
        cwd=ROOT, text=True, capture_output=True, timeout=30, check=True,
    ).stdout


def wait_idle(timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        metrics = get_json("/metrics")
        live = metrics.get("live") or {}
        if live.get("state") == "idle" and not live.get("queued"):
            return metrics
        time.sleep(1)
    raise TimeoutError("service did not become idle")


def request(body, marker, watts):
    payload = json.loads(json.dumps(body))
    payload["messages"][0]["content"] = f"[{marker}] " + payload["messages"][0]["content"]
    payload["max_tokens"] = 512
    payload["stream"] = True
    payload["stream_options"] = {"include_usage": True}
    before = wait_idle()
    known = {row.get("time") for row in before.get("requests", [])}
    started = time.monotonic()
    samples = []
    request_object = urllib.request.Request(
        URL + "/v1/chat/completions",
        json.dumps(payload, ensure_ascii=False).encode(),
        {"Content-Type": "application/json"},
    )
    last_sample = 0.0
    done = False
    first = None
    with urllib.request.urlopen(request_object, timeout=1200) as response:
        for raw in response:
            now = time.monotonic()
            if now - last_sample >= 0.2:
                try:
                    metrics = get_json("/metrics", timeout=2)
                    hardware = metrics.get("hardware") or {}
                    samples.append({
                        "at": now,
                        "gpu_power_w": hardware.get("gpu_power"),
                        "gpu_temp_c": hardware.get("gpu_temp"),
                        "gpu_util_pct": hardware.get("gpu_util"),
                        "state": (metrics.get("live") or {}).get("state"),
                    })
                except Exception:
                    pass
                last_sample = now
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            value = line[5:].strip()
            if value == "[DONE]":
                done = True
                break
            event = json.loads(value)
            if event.get("error"):
                raise RuntimeError(str(event["error"]))
            for choice in event.get("choices") or []:
                delta = choice.get("delta") or {}
                if first is None and (delta.get("content") or delta.get("reasoning_content")):
                    first = time.monotonic()
    ended = time.monotonic()
    if not done:
        raise RuntimeError("stream ended without DONE")
    metrics = wait_idle()
    backend = None
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        fresh = [
            row for row in metrics.get("requests", []) if row.get("time") not in known
        ]
        if fresh:
            backend = fresh[-1]
            break
        time.sleep(1)
        metrics = get_json("/metrics")
    if backend is None:
        raise RuntimeError("request metrics not found")
    energy_j = 0.0
    for index, sample in enumerate(samples):
        end = samples[index + 1]["at"] if index + 1 < len(samples) else ended
        power = sample.get("gpu_power_w")
        if power is not None:
            energy_j += power * max(0.0, end - sample["at"])
    return {
        "power_limit_w": watts,
        "wall_s": ended - started,
        "ttft_s": (first - started) if first else None,
        "backend": backend,
        "gpu_energy_j": energy_j,
        "gpu_power_median_w": sorted(
            s["gpu_power_w"] for s in samples if s.get("gpu_power_w") is not None
        )[len([s for s in samples if s.get("gpu_power_w") is not None]) // 2],
        "gpu_temp_max_c": max(
            (s["gpu_temp_c"] for s in samples if s.get("gpu_temp_c") is not None),
            default=None,
        ),
        "samples": samples,
        "post_state": get_json("/metrics").get("hardware"),
    }


def warm(body, marker):
    payload = json.loads(json.dumps(body))
    payload["messages"][0]["content"] = f"[{marker}-warmup] " + payload["messages"][0]["content"]
    payload["max_tokens"] = 64
    payload["stream"] = False
    request_object = urllib.request.Request(
        URL + "/v1/chat/completions",
        json.dumps(payload, ensure_ascii=False).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request_object, timeout=1200) as response:
        json.load(response)
    wait_idle()


def main():
    out = ROOT / "outputs/Strata-Hermes-nightly-20261020/power"
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / "outputs/numa-affinity-sweep-20261019/requests.jsonl"
    bodies = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
    ]
    test_body = bodies[3]
    record = {
        "started": datetime.datetime.now().astimezone().isoformat(),
        "protocol": "three paired 32K complex requests, 512 output tokens, "
                    "power changes live without engine restart",
        "sequence": [250, 180, 180, 250, 250, 180],
        "rows": [],
        "engine": get_json("/metrics")["engine"],
    }
    try:
        for index, watts in enumerate(record["sequence"]):
            print(f"POWER_SET {watts}", flush=True)
            record.setdefault("nvidia_smi_after_set", []).append(set_power(watts))
            warm(test_body, f"power-{watts}")
            print(f"POWER_REQUEST {watts}", flush=True)
            row = request(test_body, f"power-{watts}-{index}", watts)
            record["rows"].append(row)
            backend = row["backend"]
            print(
                f"POWER_RESULT {watts} wall={row['wall_s']:.1f}s "
                f"prefill={backend['prompt_tokens']/(backend['prompt_ms']/1000):.0f} "
                f"decode={backend['decode_tok_s']:.1f} "
                f"energy={row['gpu_energy_j']:.0f}J",
                flush=True,
            )
        record["status"] = "passed"
    except BaseException as error:
        record["status"] = "failed"
        record["error"] = f"{type(error).__name__}: {error}"
    finally:
        record["restore_power"] = set_power(250)
    record["finished"] = datetime.datetime.now().astimezone().isoformat()
    (out / "results.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": record["status"], "rows": len(record["rows"])}))
    raise SystemExit(0 if record["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
