# Community benchmark on NVIDIA GeForce RTX 2080 Ti + NVIDIA GeForce RTX 2080 Ti

Measured on 2026-10-14 with `tools/strata_bench.py` (suite 1, 3 runs per test, medians with ranges). Speeds are the engine's own timings; first-token times are measured by the client over HTTP. Speed only: no correctness check was run.

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
strata --pack swift-abliterated-iq3_s --native Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf --expert-profile expert-profile.bin --expert-cache auto --prefill auto --spec 4 --spec-min-p 0.5 --mtp rt --kv int8 --ple-io ram --kv-resident 32768 --resident-budget-gib 55 --vram-reserve-mib 550 --max-context 262144 --pool-workers 15 --batch-groups 1 --batch-mtp --vram-reserve-later-mib 600 --ple-gguf Qwen3.8-Flash-Next-GSQ-RCO-Q8_0-PLE-00002-of-00002.gguf --native-dense-gguf Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf --mtp-hnorm stream
```

Environment of the config: `STRATA_BF16_TC=1`, `STRATA_STAGE_TRIM=1`, `STRATA_SPLIT_RING=384`

## Method

Run by `python tools/strata_bench.py --clients 2` against the HTTP API of a Strata server (already running); model loading is not timed. One warm-up chat and a 1K prompt are discarded first. Every prompt starts with a unique tag, so the conversation cache cannot help the fresh-prompt tests.

- short chat: the three questions of `tools/ab_engine.py`, up to 100 new tokens, 3 runs
- 4K / 16K prompts: generated word lists sized by a calibration request, 24 new tokens, 3 fresh prompts each
- agent session: system prompt and four tools, then 5 turns that each add about 1500 words of a project file and continue from the model's own earlier answers (the way agent clients resend a conversation), 64 new tokens per turn, 3 sessions; the cache numbers come from the answer's usage (`cached_tokens`) and timings (`prompt_n`)
- concurrency (when run): N requests sent at the same moment, total tokens over the wall time of the burst, latency over all requests

## Results

| Configuration | Actual prompt tokens | Reused tokens | Generated tokens | Runs | Prompt tok/s median and range | Decode tok/s median and range | TTFT seconds median and range |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| short chat | 46 (43-51) | 0 | 100 (100-100) | 9 | not measured | 47.6 (22.2-62.1) | 0.84 (0.77-1.23) |
| 4K prompt, fresh | 4019 (4019-4019) | 0 (0-0) | 24 cap | 3 | 862.2 (768.5-874.5) | not measured | 4.73 (4.66-5.30) |
| 16K prompt, fresh | 16058 (16058-16058) | 0 (0-0) | 24 cap | 3 | 1226.2 (1199.4-1285.7) | not measured | 13.22 (12.60-13.48) |
| agent session, follow-up turns | 14463 (14455-14468) at the last turn | see below | up to 64 | 3 | see below | 56.5 (25.5-77.6) | 4.55 (3.50-5.37) |

Ranges are the lowest and highest of the runs; `Runs` counts requests that returned a token.

### Agent session (conversation cache)

Cache hit over the follow-up turns: 68.8 % (68.6-68.8); earlier-turn tokens read again per session: 5 (3-73) (earlier turns that the cache did not hold; the 13634 (13633-13635) new tokens of the files are read once); first turn (nothing cached) first token: 2.07 s (2.05-2.08).

| Turn (run 1) | Prompt tokens | Reused | Read | Prompt tok/s | First token (s) | Decode tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 609 | 0 | 609 | 306.0 | 2.071 | 20.6 |
| 1 | 3704 | 624 | 3080 | 618.4 | 5.06 | 25.5 |
| 2 | 5237 | 3697 | 1540 | 377.2 | 4.181 | 35.3 |
| 3 | 8681 | 5301 | 3380 | 690.4 | 4.973 | 50.7 |
| 4 | 11605 | 8744 | 2861 | 588.8 | 4.989 | 53.4 |
| 5 | 14468 | 11622 | 2846 | 586.6 | 4.998 | 32.6 |

### Concurrency: 2 clients

Total 45.6 tok/s (34.7-46.1); first token p50 1.267 s, p95 2.062 s; request latency p50 5.58 s, p95 7.339 s; errors 0. Server parallel slots: 2 (requests beyond that wait their turn).

Per-request data: `results.json`. Engine log lines from the start: `engine-log-excerpt.txt` (when this run started the server).

## Correctness and limitations

Not measured: this is a speed suite. The conversation uses the model's own replies, so token counts differ a little between runs. Machine details come from the server, `nvidia-smi`/`rocm-smi` and the OS; background load and power limits are not recorded. Total time of the suite: 205 s.
