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
| short chat | 46 (43-51) | 0 | 100 (100-100) | 9 | not measured | 43.6 (28.7-56.1) | 0.75 (0.59-1.29) |
| 4K prompt, fresh | 4019 (4019-4019) | 0 (0-0) | 24 cap | 3 | 803.0 (788.6-819.1) | not measured | 5.08 (4.97-5.17) |
| 16K prompt, fresh | 16058 (16058-16058) | 0 (0-0) | 24 cap | 3 | 1251.0 (1248.1-1270.8) | not measured | 12.96 (12.77-12.98) |
| agent session, follow-up turns | 14481 (14464-14484) at the last turn | see below | up to 64 | 3 | see below | 56.8 (19.3-79.1) | 4.40 (3.15-5.38) |

Ranges are the lowest and highest of the runs; `Runs` counts requests that returned a token.

### Agent session (conversation cache)

Cache hit over the follow-up turns: 68.6 % (68.5-68.8); earlier-turn tokens read again per session: 75 (4-145) (earlier turns that the cache did not hold; the 13635 (13633-13635) new tokens of the files are read once); first turn (nothing cached) first token: 2.17 s (2.15-2.20).

| Turn (run 1) | Prompt tokens | Reused | Read | Prompt tok/s | First token (s) | Decode tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 609 | 0 | 609 | 293.3 | 2.153 | 18.9 |
| 1 | 3704 | 621 | 3083 | 592.7 | 5.38 | 19.3 |
| 2 | 5237 | 3697 | 1540 | 428.3 | 3.672 | 43.0 |
| 3 | 8681 | 5300 | 3381 | 719.4 | 4.791 | 56.8 |
| 4 | 11597 | 8737 | 2860 | 658.4 | 4.479 | 56.4 |
| 5 | 14481 | 11635 | 2846 | 671.1 | 4.337 | 45.0 |

### Concurrency: 2 clients

Total 37.6 tok/s (23.8-41.3); first token p50 1.49 s, p95 2.581 s; request latency p50 6.717 s, p95 10.714 s; errors 0. Server parallel slots: 2 (requests beyond that wait their turn).

Per-request data: `results.json`. Engine log lines from the start: `engine-log-excerpt.txt` (when this run started the server).

## Correctness and limitations

Not measured: this is a speed suite. The conversation uses the model's own replies, so token counts differ a little between runs. Machine details come from the server, `nvidia-smi`/`rocm-smi` and the OS; background load and power limits are not recorded. Total time of the suite: 210 s.
