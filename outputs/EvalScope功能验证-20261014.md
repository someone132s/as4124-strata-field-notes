# EvalScope 功能配置与验证

已补齐 BFCL 工具调用接入、生成参数转发及 LiveCodeBench 隔离执行。测试 VM 为 10.2.23.3；Strata 模型保持 swift-1.5-abliterated-iq3_s-q8ple，GPU 服务配置未修改。没有启动正式的 300 题评测。

## 实测结果

| 项目 | 样本 | 结果 |
|---|---|---|
| BFCL v4 | multi_turn_base_0，1 道多轮题 | 官方评分通过；18 次 API 请求、23 次工具调用，接口错误 0、输出截断 0 |
| LiveCodeBench | release_v6，1873_A，1 道代码题 | 实际生成程序；Docker 沙箱执行 5 个测试用例，5/5 通过；报告 pass@1=1 |
| 沙箱独立检查 | Python 执行与 Docker 配置检查 | 返回 42；实际断网、无宿主机目录挂载、非特权、2 核配额、1 GiB 内存限制 |

这些结果只证明评测链路正常，不能用于估计模型总体能力。BFCL 的请求合计约 66.1 秒；评分依赖修复后复用了已生成的答案。代码题完整成功任务约 40.8 秒，其中模型请求约 22.4 秒，输入 574 tokens，输出 795 tokens。代码题于北京时间 2026-10-14 20:42 完成，沙箱自动删除。

## 当前配置

- 网页继续由原 Docker 服务提供：[EvalScope](http://10.2.23.3:9000)。
- 普通评测/BFCL 使用独立 worker 镜像；BFCL 2025.10.27.1，CPU 版 Torch，NumPy 1.26.4、PyArrow 21.0.0，另补齐上游遗漏的 soundfile 依赖。
- BFCL 原适配器只传温度，因此通过独立 bfcl_policy.py 转发输出上限、采样参数、随机种子、思考预算和超时；审计文件只记录参数、计数、用量、状态，不额外记录请求正文。原生评测结果仍保存公开题目及回答，便于复核。
- 代码评测驱动运行在测试 VM 的独立虚拟环境中，生成的程序在临时 Docker 沙箱中执行；网页和 worker 均未挂载 Docker socket。最初的 socket 挂载方案被自动审批拒绝，已采用上述更窄权限的方案。
- 每个代码用例超时 6 秒；沙箱池大小 1。任务检查模型身份，使用全局锁避免多个评测任务互相干扰，保存状态和报告。

## 数据加载修复

VM 只有约 3.3 GiB 内存。原始 LiveCodeBench release_v6 的全量 Parquet 转换触发 OOM，小批次转换也未解决解压时的内存需求。已从缓存原件提取固定记录，继续使用 EvalScope 原有提示词、代码执行与评分流程。

正式 20 题按 seed=20261014 的 HF 同类随机排列，从原始 1055 条记录中选择；保存题号、原始下标、来源 URL、源分片 SHA256 和样本 JSONL SHA256。固定样本约 43 MiB，并已验证 20 条记录的题号和日期类型。README 显式声明字符串字段，避免 JSON 加载器将日期自动转换成时间对象。

提取样本时曾临时增加 4 GiB 磁盘 swap，准备完成后已关闭并删除；日后模型对比直接复用固定样本，不再重复转换全量数据。失败的 smoke-code 记录保留，成功任务名为 smoke-code-fixed。

## 远程位置及后续启动方式

根目录 `/opt/evalscope`，说明在 `configs/README-evaluation.md`。

| 内容 | 路径 |
|---|---|
| BFCL 成功记录 | `outputs/jobs/smoke-bfcl/smoke-summary.json` |
| 代码成功记录 | `outputs/jobs/smoke-code-fixed/smoke-summary.json` |
| 固定代码样本和清单 | `cache/lcb-fixed/screening/` |
| 正式测试计划 | `configs/screening-plan.json` |
| worker 依赖快照 | `requirements.worker.lock.txt` |
| 代码驱动依赖快照 | `requirements.sandbox.lock.txt` |

后续授权正式评测时，普通任务使用 `systemctl start evalscope-bench@任务名`，代码任务使用 `systemctl start evalscope-code@iq3-live_code_bench`。目前仅完成小样本功能验证；正式题目、其余分类及其他模型均未评测。
