#!/usr/bin/env python3
"""Verify conversation-cache park/restore on three short requests."""

import json
import time
import urllib.request

BASE = "http://10.2.21.4:8080"
MODEL = "huihui-qwen3.8-flash-next-abliterated-ud-iq4_xs"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as response:
        return json.load(response)


def chat(text):
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": 16,
        "temperature": 0,
    }
    request = urllib.request.Request(
        BASE + "/v1/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=300) as response:
        json.load(response)
    return time.monotonic() - started


sentence = "Memory bandwidth and cache behaviour matter for inference latency. "
filler = sentence * 150
prompts = {
    "A1": "[cache-smoke-A] " + filler,
    "B1": "[cache-smoke-B] " + filler,
    "A2": "[cache-smoke-A] " + filler,
}

for name, text in prompts.items():
    elapsed = chat(text)
    cache = get("/metrics")["conversation_cache"]
    print(json.dumps({
        "step": name,
        "wall_s": round(elapsed, 2),
        "parked": cache["parked"],
        "parks": cache["parks"],
        "restores": cache["restores"],
        "bytes": cache["bytes"],
        "reused_tokens": cache["reused_tokens"],
        "last_reused": cache["last_reused"],
    }, ensure_ascii=False), flush=True)
