# AS4124 AMD uProf memory controller check

## Acquisition and method

- AMD uProf 5.3.521 official archive, `AMDuProf_Linux_x64_5.3.521.tar.bz2`.
- Size: 347,479,426 bytes. AMD published MD5 matched: `45437d8bc0b4276a0b78e28d21de23cb`.
- `bzip2 -t` passed. Extracted under `/root/codex-uprof-20261015/unpacked/`.
- AMD `AMDuProfPcm` ran in root MSR mode on PVE host kernel `7.0.14-12-pve`; CPU topology reported 2 sockets, AMD EPYC 7282, 32 cores/64 threads. MSR module/device were present.
- Collected 24 samples over a 30-second idle baseline, then two 80-second controller-monitor windows concurrent with the same LIKWID `load_avx` read workload on 16 physical cores per NUMA node. LIKWID processed 786,432,000,000 logical read bytes per run over 55.82 s and 55.40 s.
- uProf sampled at 1.2-second intervals. The load-window means below use rows 3 through 49 to focus on the benchmark interval; uProf counts all system activity, including background VMs.

## Results

| Run | LIKWID read throughput | uProf system read traffic | uProf total read+write |
|---|---:|---:|---:|
| Idle baseline | — | 1.56 GB/s | 1.87 GB/s |
| Read run 1 | 14.09 GB/s | 14.77 GB/s | 15.10 GB/s |
| Read run 2 | 14.19 GB/s | 14.73 GB/s | 15.04 GB/s |

## Requested read / write / latency fields

| Metric | Completed result | What was actually measured |
|---|---:|---|
| Read bandwidth | LIKWID 14.09 / 14.19 GB/s; uProf aggregate controller reads 14.77 / 14.73 GB/s | Two read-only `load_avx` runs; system-wide DRAM controller traffic |
| Write bandwidth | Not measured as a standalone result | The 15.10 / 15.04 GB/s uProf figures are total read+write traffic during the read workload, not write bandwidth. No write-only workload was run. |
| Memory latency | Not measured | These uProf PCM captures report bandwidth/counters, not a DRAM latency measurement. |

So the uProf run is complete for read-traffic validation only. Write-only bandwidth and memory latency remain pending; no values are inferred from the aggregate read+write counter.

During both read runs uProf saw substantial traffic on channels C, D, G, and H for each socket (roughly 1.8–1.9 GB/s read per active channel). Channels A, B, E, and F remained at 0.00 GB/s at displayed precision. This matches the recorded 4-DIMM-per-socket population C2/D2/G2/H2. Therefore only four of the eight memory channels on each socket are populated in this configuration.

Model-specific clarification (2026-10-16): EPYC 7282 is a four-channel-optimized SKU. AMD lists eight supported memory channels but 85.3 GB/s theoretical bandwidth per socket, with the datasheet footnote "Performance optimized for 4 channels with DDR4-2667 DIMMS". Four populated channels must not be interpreted as a fault or as necessarily halving the performance of this SKU; adding four DIMMs per socket is not established to double bandwidth. The published 85.3 GB/s figure is not a measured result for this machine or proof of an invariant hard cap at every memory setting. Sources: https://www.amd.com/en/support/downloads/drivers.html/processors/epyc/epyc-7002-series/amd-epyc-7282.html and https://www.amd.com/content/dam/amd/en/documents/products/epyc/amd-epyc-7002-series-datasheet.pdf .

## Interpretation and limits

Two independent monitors agree closely: LIKWID reports about 14.1 GB/s of benchmark reads, while uProf observes about 14.7 GB/s of aggregate controller reads during the same period. That agreement validates the low throughput as real traffic reaching DRAM for this workload; it does not prove the machine's maximum achievable bandwidth. uProf includes other host and VM traffic, and the channels are only half populated. The BIOS screenshots show Memory Interleaving on Auto, but do not prove the effective BIOS setting after boot. AIDA64 from PE remains a useful separate comparison because it removes the PVE/VM environment, while also changing the OS and benchmark implementation.

No BIOS, VM, Strata, NUMA, power, or memory settings were changed.

## Raw files on AS4124

`/root/codex-uprof-20261015/baseline.csv`, `load.csv`, `load2.csv`, `likwid-load.log`, `likwid-load2.log`, and `uprof-load.log` / `uprof-load2.log`.
