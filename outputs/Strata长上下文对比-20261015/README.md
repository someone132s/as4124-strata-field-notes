# 长上下文比较报告

打开 `Strata长上下文性能对比.html`，可离线浏览所有折线图、参数表与原始截图。HTML内嵌图表/图像；若需下载CSV、JSON与独立SVG，请保留整个目录。

作者归属按用户2026-10-15澄清：

- 两份 `strata-deploy-guide*.pdf` 与之前的配套全长性能曲线：7945作者。硬件截图标明Ryzen 9 7945HX。
- 最新TTFT、prefill TTFT/引擎、decode API/引擎、接受率表：单路2690v4网友。不得拼成7945作者数据。

本机数据为32K、64K、128K、192K、230K、约260000输入tokens，A/B每档3次，共36次。A为prefill auto:16384，B为auto。逐次payload hash核验18组完全相同，reused/cached tokens全0；主图取3次中位数，误差线为min–max。A/B运行时auto PCIe fraction分别0.25/0.27，不能宣称除一个变量外所有运行时条件完全相同。

外部数据：7945全长图只有标称K档位，无逐次原始计数，按K=1024暂放置；新PDF三点2600token计数任务与全长图1000token任务分开保留。2690v4图有实际prompt，最后一行虽标230.6K，实际241926 tokens，图按实际值绘制。未补造256K外部数据或TTFT。

复现：使用已配置的依赖Python（包含ReportLab）运行 `generate_report.py`。图表由ReportLab LinePlot生成，无外部CDN依赖。`comparison-data.json`包含结构化来源数据；`local-requests.csv`为本机36次请求元数据，无prompt/回答正文。

执行状态另见 `restore-verification.json`：全部性能组完成。原runner恢复验收记录的解包代码抛ValueError，原campaign保留restore-failed；独立只读/health与两份配置hash均确认已恢复。此次核查未再重启或更改GPU配置。额外pipeline-windows2双客户端补测仍待恢复验收问题处理，尚未触发。
