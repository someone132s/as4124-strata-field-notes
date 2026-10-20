# 官方 API BFCL 完成记录

2026-10-15（北京时间）。正式测试11:34:43开始，13:12:57完成。两模型顺序执行，每模型40题、四类各10题，题目与本机IQ3已完成的BFCL完全配对。

| 本次选中子集 | 官方Flash-Next API | 官方27B API | 本机Swift IQ3_S（历史同题） |
|---|---:|---:|---:|
| 多轮基础 multi_turn_base | 6/10 | 4/10 | 4/10 |
| 多轮长上下文 multi_turn_long_context | 6/10 | 4/10 | 3/10 |
| 缺少可用函数 multi_turn_miss_func | 4/10 | 0/10 | 0/10 |
| 缺少参数 multi_turn_miss_param | 4/10 | 1/10 | 3/10 |
| 本次40题 accuracy | **20/40，50.0%** | **9/40，22.5%** | **10/40，25.0%** |

这里“官方模型”指用户确认的API映射：`qwen3.8-flash`即Qwen3.8-Flash-Next，`qwen3.8-27b`即Qwen3.8-27B。本结果是自选同题筛查，**不是官方发布分数或BFCL完整排行榜分数**。

## 执行完整性

- 两份报告均requested=40、succeeded=40、errored=0、incomplete=false。
- Flash：819次API请求，780次工具调用；errors=0、truncated=0。输入5601717 tokens，输出193121 tokens。
- 27B：834次API请求，800次工具调用；errors=0、truncated=0。输入6830994 tokens，输出292682 tokens。
- BFCL多轮任务包含多次模型/工具往返，API请求数不是样本题数。
- Flash约45分29秒；27B约52分44秒。两模型测试按顺序进行。

## 参数与比较边界

API请求使用reasoning_effort=xhigh，启用thinking，max_tokens=16384，temperature=1、top_p=0.95、top_k=20、seed=20261014，每任务eval_batch_size=2。沿用IQ3题目、评分器和历史消息处理策略；原BFCL handler会从历史assistant消息剥离reasoning_content。

外部API没有发送Strata专用reasoning_budget_tokens=12288字段，因此“同最高思考控制”不等于严格相同的推理token预算。Swift IQ3_S还是经过微调/abliteration及量化的不同权重，不能把Flash的25个百分点优势全记为量化损失。

每个子类仅10题，一题改变该类别10个百分点；总分一题改变2.5个百分点。Flash本次领先明确，但27B与本机IQ3仅差一题，不能据此宣称27B稳定落后或本机IQ3全面胜出。

报告内的聚合项`OVERALL`分别为0.15/0.0675，它来自BFCL更大类别集合的加权汇总，不是本次选中40题的accuracy。这里只有四个multi-turn子类参与测试，应采用顶层accuracy与四个非聚合子类，不将其当完整BFCL总榜分数。

## 报告与追溯

- [Flash完整评分报告](flash-report.json)
- [27B完整评分报告](27b-report.json)
- [Campaign完成状态](campaign-status.json)
- [结构化比较摘要](summary.json)

远程原始结果保留在EvalScope VM `/opt/evalscope/outputs/jobs/api-flash-bfcl-20261015/` 和 `/opt/evalscope/outputs/jobs/api-27b-bfcl-20261015/`。本目录仅归档评分及元数据，不读取/复制预测正文或凭据。

其他任务状态：Strata全部长曲线已完成，服务健康且配置hash恢复；runner恢复验收记录有解包ValueError，已另存证。额外pipeline-windows2双客户端补测仍为用户已授权的待办，按此前失败停止条件尚未启动。原IQ3→UD-IQ4 campaign没有恢复或切换模型。
