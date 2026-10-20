# IQ3 编程测试结果分析
日期：2026-10-15。只读取既有结果，没有重新作答、执行代码或更改正在运行的 Strata 性能测试。

## 结论
IQ3_S + Q8 PLE 组合在这组固定20题上为20/20，单次生成 pass@1=100%；评审记录显示20题都用sandbox执行，实际记录586个测试用例、全部通过，没有失败用例或执行错误。该组包含中高难度题，足以说明部署仍能解决非简单算法编程任务；不足以据此宣称达到或超过原版全量成绩，也没有建立量化前后精度差异。

## 样本与生成条件
从release_v6累计1055题中以seed=20261014固定抽取20条原始记录；manifest保存原始行号和题号。覆盖2023-05-13至2025-03-15，LeetCode 7题、AtCoder 12题、Codeforces 1题。不是仅选easy，也不是将当前按顺序排列的原数据前20题直接用于评测。没有证据能排除这些较早题目的训练数据重叠。

每题一次生成、repeats=1、无少样本示例；temperature=1、top_p=.95、top_k=20、seed=20261014，reasoning_effort=high，思考预算24576，max_tokens=32768，双并发。high在当前Strata前端对应xhigh（此前检查过映射）。代码交给Python3.11沙箱，网络关闭、2 CPU/1GiB内存、每测试用例6秒限制。20条finish reason均为stop，没有length截断；API usage未单列reasoning_tokens，不能将总输出tokens全当作思考tokens。

## 难度与成本
| 难度 | 通过 | 记录测试用例 | 每题平均生成tokens | 每题平均响应时间 |
|---|---:|---:|---:|---:|
| easy | 9/9 | 219/219 | 890 | 36.4秒 |
| medium | 6/6 | 156/156 | 4776 | 174.0秒 |
| hard | 5/5 | 211/211 | 25274 | 936.8秒（15.6分钟） |

hard题包括Reverse Brackets、Sum of Max Matching、minimum-operations-to-make-character-frequencies-equal、Dense Buildings、Double Sum 3。5道hard占总生成tokens的77.5%，各输出约24,968–26,165 tokens；与24,576思考预算接近，提示它们用了较长的推理过程，但仅凭总token数不能断言思考预算全部用尽。

20题总输出163033tokens；每题响应时间中位54.53秒、均值302.76秒；TTFT均值2.30秒。平均数被少数难题拉高。正式任务北京时间09:32:09至10:26:26，总墙钟54分17秒。报告的26.92 tok/s是按请求累计时延计算的输出速率，不应当作整机双并发总吞吐或单请求独占硬件速度。难题的成本主要在长生成过程，短首字时间无法解决这个成本。

## 公开横向参考
| 发布方及模型 | LiveCodeBench v6 |
|---|---:|
| UkisAI Swift1.5 Flash-Next BF16 | 90.39% |
| UkisAI同协议Flash-Next base BF16 | 88.40% |
| Qwen官方Flash-Next | 91.9% |
| Qwen官方27B | 90.3% |
| Qwen表内DeepSeek-V4-Flash-0731 | 90.6% |
| Qwen表内Claude-Opus-4.6 (Max) | 88.8% |

[Swift原版模型卡](https://huggingface.co/ukisai/Swift1.5-Qwen3.8-Flash-Next#evaluation)明确：BF16、full release_v6、五seed平均pass@1、xhigh、MTP关闭、输出cap100000。90.39与88.40是同一发布方同协议对照。我们的权重还含abliteration、量化和外置Q8 PLE，比较部署组合时不能将差别只归因于IQ3量化。

[Qwen官方Flash-Next表](https://huggingface.co/Qwen/Qwen3.8-Flash-Next#benchmark-results)及[27B表](https://huggingface.co/Qwen/Qwen3.8-27B#text-performance)提供其余分数；LCB行没有完整披露具体日期子窗口、seed和生成预算。因此只能参考大致量级，不能与本地20题直接排名。Swift发布方base88.40与Qwen发布方91.9不是同一套完整评测协议，不构成互相矛盾的同一实测。

20题每题占5个百分点。即使假定模型真实通过率为90%、每题独立且等概率，连续20题全对的概率仍为0.9^20≈12.2%。这只是帮助理解小样本的示例，并非对真实异质题目的统计建模。100%小样本不能推出超过全量90%左右的模型。

## 对部署选择的含义
目前可以认定这组题没有暴露算法代码生成能力的明显故障，并看到较高的难题生成成本。不能据此认定量化无损、日常工程能力全通过，或Hermes长程工具任务可靠。LiveCodeBench偏独立算法题，与BFCL多轮状态/工具选择覆盖不同。针对用户编程次要、Agent优先的需求，后续模型复用同20题即可；若同样20/20应视为本组打平，再比较成本。无需为了证明细小差别立即扩充编程测试。

## 追溯
- 本地元数据审计：[LiveCodeBench本地结果审计-20261015.json](./LiveCodeBench本地结果审计-20261015.json)
- 公开来源详情：[LiveCodeBench公开对比调研-20261015.md](./LiveCodeBench公开对比调研-20261015.md)
- EvalScope VM报告：/opt/evalscope/outputs/jobs/iq3-live_code_bench/evaluation/reports/swift-1.5-abliterated-iq3_s-q8ple/live_code_bench.json
- 同目录predictions与reviews子目录保存既有生成及判分；本文未复制题目、代码或思考正文。
- 样本manifest：/opt/evalscope/cache/lcb-fixed/screening/manifest.json

