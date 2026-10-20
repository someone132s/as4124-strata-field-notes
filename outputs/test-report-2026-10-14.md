# Strata 部署测试结果（2026-10-14）

## 结论

在本轮固定负载下，`--batch-groups 1 --batch-mtp` 的双并发表现明显好于流水线 `--batch-groups 2`：同时提交两条请求时，MTP 的每对请求总吞吐中位数为 **22.19 tok/s**，A1/A2 流水线分别为 **10.94 / 10.85 tok/s**，约 **2.04 倍**。第一条请求开始生成后再提交第二条长输入时，MTP 为 **22.19 tok/s**，流水线 A1/A2 为 **13.59 / 13.19 tok/s**，约 **1.66 倍**。A1 与 A2 结果接近，说明流水线基线具有较好的重复性。

这支持在当前机器上进一步考虑 MTP 调度，但结论只适用于本模型、当前 Strata 版本和这套文本负载；尚未验证真实多人混合长度/图像请求下的服务质量。本轮**没有把 MTP 配置留在服务上**。

## 调度对照方法

测试前后均保持模型 `huihui-qwen3.8-flash-next-abliterated-ud-iq4_xs`、15 workers、2 并发槽、256K 上下文、CPU vision、vision max tokens 1024、`STRATA_BF16_TC=1`、24/24 固定层分配、PCIe 0.28、8192-token prefill chunk。请求使用相同课本文本和固定问题集合，温度 0.2、top-p 0.95、top-k 20、seed 20261014、reasoning off、每条最多生成 1024 tokens。请求和回答正文没有写入报告；保存的是哈希、token/字符数、计时和引擎指标。

采用 A-B-A：流水线 A1 → 单组＋batch MTP B → 流水线 A2。每臂各有三组同时提交的双请求，以及三组“第一条已开始生成后再发第二条长输入”的错峰双请求。每对输出合计除以从首条提交到两条都完成的墙钟时间，作为该对总吞吐；同时记录完成时间中位数和同时解码槽峰值。所有正式样本均确认达到两个同时解码槽，backend 未复用 prompt 前缀。

| 调度臂 | 同时提交：吞吐中位数 | 同时提交：每对耗时中位数 | 错峰：吞吐中位数 | 错峰：每对耗时中位数 |
|---|---:|---:|---:|---:|
| 流水线 A1 | 10.94 tok/s | 187.2 s | 13.59 tok/s | 150.7 s |
| 单组＋MTP B | 22.19 tok/s | 92.3 s | 22.19 tok/s | 92.3 s |
| 流水线 A2 | 10.85 tok/s | 188.7 s | 13.19 tok/s | 155.2 s |

错峰的流水线吞吐高于同时提交场景，是因为第二个长 prompt 在第一条已经生成一段后才加入，两个请求的重叠时间较短；MTP 在这两种到达模式下接近相同。MTP 日志确认 `--batch-mtp` 的 slot drafters 实际启用，未被引擎拒绝。

## 阶段权重裁剪测试

测试固定 24/24 层分配和 PCIe 0.28，比较 `STRATA_STAGE_TRIM=0 → 1 → 0`。裁剪开启后专家缓存由 **28,506 MiB / 12,333 slots** 增至 **32,913 MiB / 14,235 slots**：增加 **4,407 MiB（约 15.5%）**和 **1,902 slots（约 15.4%）**。这证实裁剪策略为热专家缓存提供了更多容量。

| 臂 | Trim | 专家缓存 | 串行 backend decode 中位数 | 串行预填充中位数 |
|---|---:|---:|---:|---:|
| A1 | 0 | 28,506 MiB / 12,333 slots | 41.5 tok/s | 1,047 tok/s |
| B | 1 | 32,913 MiB / 14,235 slots | 48.8 tok/s | 1,146 tok/s |
| A2 | 0 | 28,506 MiB / 12,333 slots | 42.4 tok/s | 1,079 tok/s |

B 的串行 decode 比 A1/A2 均值约快 16%，但单臂的串行请求仅三条，速度仍会受生成差异和时序影响，应视为积极信号而非已证明的普遍提升。A1 在测试脚本补上双请求组之前就已结束，所以裁剪的并发数据只有 B 对 A2 的一组比较：B 总吞吐 39.00 tok/s，A2 为 34.81 tok/s；这不是完整 A-B-A 双请求对照，不能据此单独下因果结论。

## 测试过程中的脚本问题

第一次调度试跑的同时到达 A1 样本通过，但错峰触发器监听了该版本并不更新的 `slots[].state` 字段，因此未提交第二条请求并触发断言。检查实际指标后将触发条件改为全局 `state=generating` 且 `generated>0`，做了语法检查并重新完整执行 A-B-A。该失败试跑不计入正式比较。

阶段裁剪脚本在恢复原自动分层配置时，也因恢复校验错误地要求 PCIe 必须是测试臂固定值 0.28 而报 `AssertionError`。当时配置文件已经恢复；随后调度测试完成后再次核验，原配置和 Compose 都与备份逐字节一致，Strata 接口健康且 idle。因此阶段裁剪报告里的 `restored_healthy=false` 是校验器的假阴性，不是配置未恢复。最终调度报告的 `restored_exact_config=true` 和 `restored_healthy=true`。

## 最终服务状态

Strata 保持健康并处于 idle，服务配置文件和 `compose.yaml` 均与调度测试前备份完全一致。运行参数核验为：15 workers、2 槽、自动分层、256K 上下文、CPU vision 1024、`STRATA_BF16_TC=1`；`STRATA_STAGE_TRIM` 未留在测试值。MySQL 与 Redis 持续运行，测试脚本只重建了 Strata 容器。

## 原始记录

原始 JSON 不含请求或回答正文，可用于复核各请求计时、计数、哈希、引擎快照和启动日志摘录：

- `remote-results/scheduler-ababa-20261014-120432.json`：调度 A-B-A 总报告。
- `remote-results/scheduler-pipeline-20261014-120432-pipeline-A1.json`、`...-pipeline-A2.json`：流水线样本。
- `remote-results/scheduler-single-mtp-20261014-120432-single-mtp-B.json`：MTP 样本。
- `remote-results/stage-trim-aba-20261014-110028.json`：裁剪测试总报告。
- `remote-results/turing-confirm-baseline-20261014-110555.json`、`...-111338.json`、`...-112632.json`：裁剪 A1/B/A2 各臂详细记录。
