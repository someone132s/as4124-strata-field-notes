# DeepSeek BFCL 输出截断后的恢复

2026-10-15 19:20（Asia/Shanghai）启动显式恢复。

原任务 `api-deepseek41f-bfcl-20261015` 完成 11/40 条完整预测后中止。状态记录为 `AbortAPI`，237 次请求、传输错误 0、输出截断 1。实际脚本遇到 `finish_reason=length` 会抛出终止整个任务的异常；这是已复现的中止路径。未读取或输出请求、回答、推理正文，也未继续执行被审批拦截的审计文件读取。

恢复只将后续请求输出上限从 16384 提高到 32768。保持 `deepseek-v4.1-flash`、`reasoning_effort=max`、thinking enabled、并发 2、题目/随机种子/评分器不变。保留思考历史的 API 适配保持原样。若再次遇到截断或传输故障仍停止，不进行无限重试。

恢复预检使用 EvalScope 原生 `ModelResult.to_task_state()` 验证了所有缓存，并逐题校验与历史 IQ3 相同的 40 题哈希：base 9 条、long_context 2 条，合计 11 条可复用；剩余 29 条重新执行未完成题目的完整流程。不会重跑已完成的 11 条。由于 generation_config 变化，使用 EvalScope 显式 `rerun_review=True` 复用预测并重新评分。

原始脚本备份：`/opt/evalscope/configs/run_deepseek_bfcl.pre-recovery-20261015.py`。

原任务状态、配置、进度及恢复清单归档：
`/opt/evalscope/outputs/jobs/api-deepseek41f-bfcl-20261015/recovery-output-cap-32768/`。

新服务：`evalscope-deepseek-bfcl-resume-20261015.service`。
结果和用户原来的 progress.json / job-state.json 路径保持一致。

统计口径：已复用 11 题原本上限为 16384，后续 29 题上限为 32768。最终成绩应标为“恢复后、提高输出预算的参考结果”，不可称为与本地/Qwen 相同输出预算的严格对照。旧尝试的截断和用量单列 `previous_attempt_transport`，不会隐去。`transport` 为本次恢复执行的统计，在任务结束时写入。

验证：离线回归 `work/evalscope-docker/test_deepseek_output_budget.py`，修复前能够复现整项 AbortAPI，修复后通过；没有为诊断额外请求线上模型。恢复预检通过；启动后服务 active/running，任务与进度均为 running。启动时缓存任务需要经过恢复/重评分阶段，进度数字短暂小于 11 并不表示原缓存被删除。

依照用户偏好，本次仅验证恢复启动，不创建 DeepSeek 定时监控。
