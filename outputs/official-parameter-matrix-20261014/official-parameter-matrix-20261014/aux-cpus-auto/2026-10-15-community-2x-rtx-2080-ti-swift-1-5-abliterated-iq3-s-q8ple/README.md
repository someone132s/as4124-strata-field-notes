# Community benchmark on NVIDIA GeForce RTX 2080 Ti + NVIDIA GeForce RTX 2080 Ti

Measured on 2026-10-15 with `tools/strata_bench.py` (suite 1, 3 runs per test, medians with ranges). Speeds are the engine's own timings; first-token times are measured by the client over HTTP. Speed only: no correctness check was run.

## Hardware and software

- GPU and VRAM: NVIDIA GeForce RTX 2080 Ti + NVIDIA GeForce RTX 2080 Ti, 44 GiB VRAM
- CPU: AMD EPYC 7282 16-Core Processor (32 cores, 32 threads); installed RAM: 125.8 GiB; storage: not measured
- OS: Linux 6.1.0-53-amd64; GPU driver: 580.159.04; CUDA: 13.0
- Strata: project 0.1.43.1, commit a0116b27; engine 0.1.43.1
- Background workloads and power limits: not recorded

## Model and configuration

- Model and quantization: swift-1.5-abliterated-iq3_s-q8ple
- Context: 262144 tokens; parallel slots: 2
- Settings: the install's own configuration, unchanged; thinking off for the suite; temperature 0

```text
strata --pack swift-abliterated-iq3_s --native Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf --expert-profile expert-profile.bin --expert-cache auto --prefill auto --spec 4 --spec-min-p 0.5 --mtp rt --kv int8 --ple-io ram --kv-resident 32768 --resident-budget-gib 55 --vram-reserve-mib 550 --max-context 262144 --pool-workers 15 --batch-groups 1 --batch-mtp --vram-reserve-later-mib 600 --ple-gguf Qwen3.8-Flash-Next-GSQ-RCO-Q8_0-PLE-00002-of-00002.gguf --native-dense-gguf Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf --mtp-hnorm stream --aux-cpus auto
```

Environment of the config: `STRATA_BF16_TC=1`, `STRATA_STAGE_TRIM=1`

## Method

Run by `python tools/strata_bench.py --clients 2` against the HTTP API of a Strata server (already running); model loading is not timed. One warm-up chat and a 1K prompt are discarded first. Every prompt starts with a unique tag, so the conversation cache cannot help the fresh-prompt tests.

- short chat: the three questions of `tools/ab_engine.py`, up to 100 new tokens, 3 runs
- 4K / 16K prompts: generated word lists sized by a calibration request, 24 new tokens, 3 fresh prompts each
- agent session: system prompt and four tools, then 5 turns that each add about 1500 words of a project file and continue from the model's own earlier answers (the way agent clients resend a conversation), 64 new tokens per turn, 3 sessions; the cache numbers come from the answer's usage (`cached_tokens`) and timings (`prompt_n`)
- concurrency (when run): N requests sent at the same moment, total tokens over the wall time of the burst, latency over all requests

## Results

| Configuration | Actual prompt tokens | Reused tokens | Generated tokens | Runs | Prompt tok/s median and range | Decode tok/s median and range | TTFT seconds median and range |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| short chat | 46 (43-51) | 0 | 100 (100-100) | 9 | not measured | 45.3 (20.4-65.0) | 0.82 (0.56-1.58) |
| 4K prompt, fresh | 4019 (4019-4019) | 0 (0-0) | 24 cap | 3 | 881.1 (880.0-895.1) | not measured | 4.62 (4.56-4.63) |
| 16K prompt, fresh | 16058 (16058-16058) | 0 (0-0) | 24 cap | 3 | 1334.2 (1316.6-1349.3) | not measured | 12.15 (12.02-12.31) |
| agent session, follow-up turns | 14480 (14430-14480) at the last turn | see below | up to 64 | 3 | see below | 53.0 (22.0-81.8) | 4.43 (3.37-5.09) |

Ranges are the lowest and highest of the runs; `Runs` counts requests that returned a token.

### Agent session (conversation cache)

Cache hit over the follow-up turns: 68.6 % (68.6-68.8); earlier-turn tokens read again per session: 74 (3-75) (earlier turns that the cache did not hold; the 13635 (13635-13636) new tokens of the files are read once); first turn (nothing cached) first token: 2.26 s (2.20-2.33).

| Turn (run 1) | Prompt tokens | Reused | Read | Prompt tok/s | First token (s) | Decode tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 609 | 0 | 609 | 286.0 | 2.261 | 20.4 |
| 1 | 3704 | 621 | 3083 | 721.3 | 4.377 | 22.0 |
| 2 | 5237 | 3697 | 1540 | 433.5 | 3.65 | 29.9 |
| 3 | 8681 | 5300 | 3381 | 699.3 | 4.977 | 33.4 |
| 4 | 11567 | 8707 | 2860 | 693.5 | 4.288 | 56.7 |
| 5 | 14430 | 11584 | 2846 | 650.9 | 4.5 | 32.5 |

### Concurrency: 2 clients

Total 36.4 tok/s (27.6-39.5); first token p50 1.558 s, p95 2.24 s; request latency p50 6.934 s, p95 9.235 s; errors 0. Server parallel slots: 2 (requests beyond that wait their turn).

Per-request data: `results.json`. Engine log lines from the start: `engine-log-excerpt.txt` (when this run started the server).

## Correctness and limitations

Not measured: this is a speed suite. The conversation uses the model's own replies, so token counts differ a little between runs. Machine details come from the server, `nvidia-smi`/`rocm-smi` and the OS; background load and power limits are not recorded. Total time of the suite: 204 s.
