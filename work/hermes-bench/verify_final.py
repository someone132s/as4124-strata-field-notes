#!/usr/bin/env python3
"""Capture the final read-only state after the overnight test."""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/Strata-Hermes-nightly-20261020"
SSH = [
    "ssh", "-i", "work/id_ed25519_pve_local", "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
    "-o", "UserKnownHostsFile=work/known_hosts_vm502", "root@10.2.21.4",
]


def remote(command):
    result = subprocess.run(
        SSH + [command], cwd=ROOT, text=True, capture_output=True, timeout=60
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main():
    config_path = ROOT / "outputs/author-profile-20261019/original-config.json"
    remote_config = "/opt/strata-data/config/strata-huihui-ud-iq4_xs-q8ple-vision-v0.1.45.json"
    with urllib.request.urlopen("http://10.2.21.4:8080/health", timeout=20) as response:
        health = json.load(response)
    with urllib.request.urlopen("http://10.2.21.4:8080/metrics", timeout=20) as response:
        metrics = json.load(response)
    process = remote("pgrep -af '^/opt/strata/engine/strata --serve'")
    pid = int(process["stdout"].split(None, 1)[0])
    environ = remote(f"tr '\\0' '\\n' < /proc/{pid}/environ")
    selected_env = {}
    for line in environ["stdout"].splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key.startswith("STRATA_") or key == "CUDA_VISIBLE_DEVICES":
                selected_env[key] = value
    state = {
        "captured": datetime.datetime.now().astimezone().isoformat(),
        "health": health,
        "engine": metrics.get("engine"),
        "live": metrics.get("live"),
        "hardware": metrics.get("hardware"),
        "config_remote": remote_config,
        "local_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "remote_config": remote(f"sha256sum {remote_config}"),
        "process": process,
        "selected_engine_env": selected_env,
        "nvidia_smi": remote(
            "nvidia-smi --query-gpu=uuid,name,power.limit,power.default_limit,"
            "power.draw,temperature.gpu,memory.used,memory.total --format=csv,noheader"
        ),
        "power_service_enabled": remote("systemctl is-enabled nvidia-power-limit.service"),
        "power_service_active": remote("systemctl is-active nvidia-power-limit.service"),
        "boot_id": remote("cat /proc/sys/kernel/random/boot_id"),
        "uptime": remote("uptime"),
        "memory": remote("free -h"),
        "strata_container": remote(
            "docker ps --filter name=strata-deploy-strata-1 --format "
            "'{{.Names}}|{{.Status}}|{{.Ports}}'"
        ),
    }
    expected_sha = state["local_config_sha256"]
    state["config_matches_b0"] = expected_sha in state["remote_config"]["stdout"]
    state["power_limits_ok"] = (
        "250.00 W, 250.00 W" in state["nvidia_smi"]["stdout"].splitlines()[1]
        and "250.00 W, 250.00 W" in state["nvidia_smi"]["stdout"].splitlines()[2]
    )
    state["status"] = (
        "passed"
        if health.get("status") == "ok"
        and health.get("loaded")
        and state["config_matches_b0"]
        and state["power_limits_ok"]
        and state["power_service_enabled"]["returncode"] != 0
        and state["power_service_active"]["returncode"] != 0
        else "failed"
    )
    (OUT / "final-verification.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": state["status"],
        "config_matches_b0": state["config_matches_b0"],
        "power_limits_ok": state["power_limits_ok"],
        "health": health.get("status"),
    }, ensure_ascii=False))
    raise SystemExit(0 if state["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
