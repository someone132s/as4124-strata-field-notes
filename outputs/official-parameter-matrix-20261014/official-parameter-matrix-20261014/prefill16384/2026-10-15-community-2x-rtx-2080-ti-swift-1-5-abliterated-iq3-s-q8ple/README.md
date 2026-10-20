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
strata --pack swift-abliterated-iq3_s --native Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf --expert-profile expert-profile.bin --expert-cache auto --prefill auto:16384 --spec 4 --spec-min-p 0.5 --mtp rt --kv int8 --ple-io ram --kv-resident 32768 --resident-budget-gib 55 --vram-reserve-mib 550 --max-context 262144 --pool-workers 15 --batch-groups 1 --batch-mtp --vram-reserve-later-mib 600 --ple-gguf Qwen3.8-Flash-Next-GSQ-RCO-Q8_0-PLE-00002-of-00002.gguf --native-dense-gguf Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf --mtp-hnorm stream
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
| short chat | 46 (43-51) | 0 | 100 (100-100) | 9 | not measured | 47.5 (19.3-59.5) | 1.06 (0.93-1.59) |
| 4K prompt, fresh | 4019 (4019-4019) | 0 (0-0) | 24 cap | 3 | 710.9 (704.9-716.3) | not measured | 5.75 (5.72-5.79) |
| 16K prompt, fresh | 16058 (16058-16058) | 0 (0-0) | 24 cap | 3 | 895.9 (891.4-920.8) | not measured | 18.04 (17.63-18.13) |
| agent session, follow-up turns | 14478 (14438-14499) at the last turn | see below | up to 64 | 3 | see below | 56.9 (25.6-74.2) | 4.91 (3.52-5.42) |

Ranges are the lowest and highest of the runs; `Runs` counts requests that returned a token.

### Agent session (conversation cache)

Cache hit over the follow-up turns: 68.8 % (68.8-68.8); earlier-turn tokens read again per session: 3 (2-3) (earlier turns that the cache did not hold; the 13633 (13633-13635) new tokens of the files are read once); first turn (nothing cached) first token: 2.12 s (2.08-2.15).

| Turn (run 1) | Prompt tokens | Reused | Read | Prompt tok/s | First token (s) | Decode tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 609 | 0 | 609 | 303.6 | 2.121 | 19.0 |
| 1 | 3704 | 622 | 3082 | 635.8 | 5.033 | 25.6 |
| 2 | 5237 | 3767 | 1470 | 423.5 | 3.625 | 29.1 |
| 3 | 8681 | 5301 | 3380 | 646.9 | 5.422 | 39.0 |
| 4 | 11591 | 8731 | 2860 | 596.0 | 4.953 | 40.5 |
| 5 | 14478 | 11632 | 2846 | 591.0 | 4.943 | 38.0 |

### Concurrency: 2 clients

Total 38.0 tok/s (26.6-38.8); first token p50 1.557 s, p95 2.637 s; request latency p50 6.684 s, p95 9.541 s; errors 0. Server parallel slots: 2 (requests beyond that wait their turn).

Per-request data: `results.json`. Engine log lines from the start: `engine-log-excerpt.txt` (when this run started the server).

## Correctness and limitations

Not measured: this is a speed suite. The conversation uses the model's own replies, so token counts differ a little between runs. Machine details come from the server, `nvidia-smi`/`rocm-smi` and the OS; background load and power limits are not recorded. Total time of the suite: 241 s.
