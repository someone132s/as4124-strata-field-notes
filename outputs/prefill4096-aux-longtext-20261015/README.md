# Strata: fixed 4096 prefill and aux-cpus long-text tests — 2026-10-15

Model: `swift-1.5-abliterated-iq3_s-q8ple`, engine 0.1.43.1, 262144 context, images off, 15 workers, batch 2, KV int8 with 32768 resident, `--mtp-hnorm stream`, auto layer split. Each candidate was tested once; the existing baseline was not rerun.

## Fixed 4096 prefill (official Strata benchmark)

The requested `--prefill auto:4096` does not lower the default chunk in this Strata version: `auto:N` only raises the default 8192 ceiling. To test a real 4096-token chunk, the run used fixed `--prefill 4096`; the engine argv confirms this. It was then restored to `--prefill auto`.

| Metric | Existing official baseline | Fixed 4096 | Change |
|---|---:|---:|---:|
| Short-chat decode median | 43.60 tok/s | 57.30 tok/s | +31.4% |
| Short-chat first token median | 0.75 s | 0.65 s | -13.4% |
| 4K prompt prefill median | 803 tok/s | 831.4 tok/s | +3.5% |
| 4K prompt first token median | 5.08 s | 4.91 s | -3.2% |
| 16K prompt prefill median | 1251 tok/s | 1212 tok/s | -3.1% |
| 16K prompt first token median | 12.96 s | 13.39 s | +3.3% |
| Agent turn decode median | 56.8 tok/s | 58.1 tok/s | +2.3% |
| Two-client aggregate median | 37.56 tok/s | 42.11 tok/s | +12.1% |

The 4K/16K prompt results are close and move in opposite directions; this does not show a robust long-prompt benefit from a fixed 4096 chunk. Short-chat and aggregate-concurrency results improved in this run, but the variance and one-run design make those changes suggestive only.

## `--aux-cpus auto` (own long-text script)

Restored the baseline and added only `--aux-cpus auto`. The startup log confirmed auxiliary threads assigned to logical CPUs 16–31. Reused the prior long-text protocol and exact source text: two warmups, then three formal ~19.7K-token prompts, 1024 output tokens each, temperature 0, fixed sampling seed.

| Metric | Existing `hnorm stream` baseline | `aux-cpus auto` | Change |
|---|---:|---:|---:|
| Decode median | 61.3 tok/s | 65.5 tok/s | +6.9% |
| Weighted prefill | 1248.2 tok/s | 1277.0 tok/s | +2.3% |
| TTFT median | 15.78 s | 15.58 s | -1.2% |
| End-to-end throughput | 31.76 tok/s | 32.82 tok/s | +3.3% |
| Expert hit-rate median | 98.5% | 98.4% | -0.1 pp |

This is a small positive result in the long-text workload, especially decode, but it is only three formal samples in one run. It does not establish a repeatable gain. The minimum free VRAM reported during the run was 134 MiB on GPU 0 and 80 MiB on GPU 1, so the service remains close to its VRAM headroom warning threshold.

## Final state

The campaign completed both phases. It left the baseline configuration plus `--aux-cpus auto`; `--prefill` is back to `auto`. The service health check returned `ok`, model loaded, images disabled, and 262144 context.

Raw campaign JSON: [campaign.json](campaign.json)

Official Strata report: [official-README.md](official-README.md)
