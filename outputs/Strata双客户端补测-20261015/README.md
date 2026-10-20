# Strata 双客户端 pipeline-windows=2 补测

日期：2026-10-15（Asia/Shanghai）

## 测法

在恢复后的 IQ3 基线下，比较既有 `current-batch` 数据和新补测的 `pipeline-windows=2`。两组都使用相同课本、问题轮换、同时到达/错峰到达两种负载、随机种子 20261014、temperature 0.2、top-p 0.95、top-k 20、单请求最多 1024 个输出 token。每种到达方式各3对正式请求。所有请求均成功完成，统计 prompt cache reuse 为0。

`pipeline-windows=2` 使用 parallel=1、layer-split=auto、关闭 batch、开启 pipeline windows 2；保留15 workers、auto prefill、KV int8/驻留32768、256K上下文、BF16-TC编译引擎与基线的 `mtp-hnorm stream`、`aux-cpus auto`。本次运行观察到 PCIe fraction 0.26；current-batch 对照记录0.28。

## 结果

| 到达方式 | current-batch aggregate tok/s | pipeline-windows=2 aggregate tok/s | 吞吐变化 | current batch中位两请求墙钟 | pipeline2中位两请求墙钟 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 同时到达 | 28.03 | 34.14 | +21.8% | 71.43 s | 58.65 s |
| 错峰到达 | 28.37 | 34.81 | +22.7% | 70.74 s | 58.60 s |

总吞吐按一对请求完成的总输出 token 除以从第一条请求提交到两条都结束的墙钟时间计算。pipeline2 每种方式各3对，总输出分别为5992和6076 tokens；三次正式配对中位吞吐分别为34.18和34.95 tok/s。

## 解读与限制

pipeline2 明显改善了这组双客户端负载的总完成速度。服务指标显示它会排队：配对期间 queued 峰值为1。由于 pipeline 配置下 `/metrics` 返回的逐槽 `slots` 数组为空，不能从这套指标直接报告“两个活跃解码槽”；这也符合 parallel=1 的预期。current-batch 确实观察到两个解码槽同时活动。

样本量只有每种负载3对，且两次运行的 PCIe fraction 略有差异，因此把约22%看作这组工作负载上的强信号，仍建议用日常真实请求复核。这个结论支持把 pipeline2 用于接下来的双并发 BFCL 运行，不代表所有单会话或其他工作负载都提升22%。

第一次启动只完成了一个预热配对，随后因脚本错误地要求 metrics 必须提供逐槽状态而中止；该尝试未计入正式结果。修正遥测判定后，第二次运行的六对正式请求全部完成。

## 恢复验收

补测 runner 最终写入 `RESTORE_PASS`。Strata 已恢复到 IQ3、images=false、max_context=262144，配置文件 SHA-256 为 `64e0608fefa206395b7ec3ae6815a86e1b325dd714346780df80c34977bfd0d5`，compose 文件 SHA-256 为 `6da533cd4aae0b9210422a78ebf8e59a9766d1ddc7541ed6be1f676073cb278b`，与补测前一致。服务健康且 idle。

原始数值和逐请求计数/时延见 `current-batch-concurrency.json`、`pipeline-windows2-dual-client.json`；运行和恢复记录见 `campaign.json`。这些文件只包含统计元数据，不保存 prompt 或回答正文。