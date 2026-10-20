# SC117 + Q8 PLE 夜间质量评测（2026-10-16，北京时间）

状态：全部完成，服务退出码为 0。北京时间 2026-10-16 01:14:51 开始，03:45:34 完成 BFCL，04:01:27 完成全部测试，总耗时约 2 小时 47 分钟。

## 完成结果

| BFCL 子集 | 正确数 |
|---|---:|
| 基础多轮 | 4/10 |
| 长上下文多轮 | 5/10 |
| 缺失函数 | 0/10 |
| 缺失参数 | 3/10 |
| 合计 | 12/40（30%） |

40/40 均成功执行和评分。BFCL 共 706 次模型请求、695 次工具调用，0 请求错误、0 输出截断。

额外工具验收 6/6；长上下文正确性 9/9，均无输出截断。三档实际输入分别为约 32.4–32.6K、129.5–129.9K、241.6–243.0K tokens。均为合成材料的定点检索、两处关联及末尾指令检查，不能外推为所有长文理解任务的正确率。

同题历史总分：Swift IQ3_S + Q8 PLE 为 10/40，Huihui UD-IQ4_XS 为 15/40，Qwen3.8-Flash API 为 20/40，DeepSeek API 为 17/40。SC117 本轮用了更大的思考/输出预算，不能把分数差异归因于单一模型或 PLE 因素。

已取回本机归档：`job-state.json`、`bfcl-score-summary.json`、`quality-summary.json`、`transport-state.json`。归档仅含评分、状态及请求计数/usage 元数据，没有取回评测请求、回答或思考正文。

检查时 GPU 服务仍加载 SC117 + Q8 PLE，健康，idle，队列为 0；未触发其他测试。

## 模型与加载验证

- 模型：SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF，非 Swift，IQ3_S。
- 固定 revision：`eec4e10a2c29b440a2ae85591fa11569ce752963`。
- 下载清单全部 verified，合计 85,595,545,635 字节；检查时磁盘文件大小与清单一致。
- 使用原有外置 Q8_0 PLE，文件为 `/opt/strata-data/models/Qwen3.8-Q8_0/Qwen3.8-Flash-Next-GSQ-RCO-Q8_0-PLE-00002-of-00002.gguf`。
- Q8 与 SC117 自带 IQ4_NL PLE 形状均为 `[160, 320001536]`。抽查 12 行，非零样本最低余弦相似度约 0.996255；本次没有重新计算外置 Q8 文件完整 SHA256。
- SC117 单独生成 native pack，配套使用其 `strata/rt` MTP。健康检查和真实工具调用回环均通过。
- 显式指定 `--native-dense-gguf` 为 SC117 第一分片，避免自动发现把两个 PLE 分片都计入 dense 加载而触发分片编号重复。未修改模型权重或引擎代码。
- 保持原有内存、CPU、上下文 262144、视觉关闭和 pipeline-windows 2 设置。
- 旧 Huihui 配置备份：GPU VM `/opt/strata-deploy/backups/sc117-q8ple-eval-20261016/`。

## 顺序与预算

1. BFCL：同原 IQ3/Huihui 四类各 10 题，共 40 题；逐题哈希校验通过。保留原采样参数、seed、并发 2 和评分器。每次请求思考预算 32768，总输出上限 49152。
2. 工具验收 6 项：单工具回环、连续工具调用、缺参数追问、缺工具不乱调用、严格 JSON、两工具组合。
3. 长上下文正确性 9 项：约 32K、128K、240K 输入，各测试随机事实检索、两处事实关联、末尾指令遵循。记录实际输入 token 数，不评分速度。

额外验收使用 4096 思考 / 8192 总输出预算、temperature=0；不和主 BFCL 的 32K 思考预算混淆。模型答错计入正确率并继续；服务错误、截断、模型身份变化则停止，不自动换模型、加预算或重跑。

这轮同时改变模型、PLE 组合及预算，不能把分数差异全部归因于模型本身。

## 收集位置（EvalScope VM：10.2.23.3）

服务：`evalscope-sc117-overnight-20261016.service`

结果根目录：`/opt/evalscope/outputs/jobs/sc117-iq3s-q8ple-bfcl32k-20261016/`

- `job-state.json`：整个流程的状态、阶段、评分摘要。
- `evaluation/progress.json`：BFCL 题目进度。
- `transport-state.json`：实时请求、错误、截断及 token 计数。
- `bfcl-score-summary.json`：BFCL 完成后的评分和执行状态摘要。
- `quality-summary.json`：工具及长上下文验收结果。
- `dataset-preflight.json`：同题校验。

可查看：

```bash
cat /opt/evalscope/outputs/jobs/sc117-iq3s-q8ple-bfcl32k-20261016/job-state.json
cat /opt/evalscope/outputs/jobs/sc117-iq3s-q8ple-bfcl32k-20261016/transport-state.json
```

## 同时确认的 DeepSeek 结果

DeepSeek 同题 BFCL 已完成 40/40，总分 42.5%（17/40）。最后一段续跑 236 次请求，0 错误、0 截断。早期 11 题来自 16384 总输出上限，后续提高至 32768，因此保留其混合预算参考的说明。
