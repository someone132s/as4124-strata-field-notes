# 4070 Ti SUPER / 5950X / P2 并发案例

来源：用户2026-10-15提供的正文与核心启动参数截图。仅资料分析，无本机配置变更或新增测试。

## 作者配置片段与主张

- RTX4070TiSUPER16GB、Ryzen95950X、64GB DDR4；未注明引擎版本、量化、完整模型和请求指标。
- max-context262144、kv int8、kv-resident32768、resident-budget-gib36、prefill auto、pcie-frac0.55、spec4、config parallel2。模型/expert-profile/MTP/vision等路径在图片中明确省略。
- 作者目的为主Agent与一个Subagent并行推进，称第二槽约增加3.1GB状态；文本host/7workers放一个CCD，视觉8核放另一个CCD。

## 上游核对

https://github.com/Niko1221/Strata/blob/v0.1.43.1/docs/BATCHING.md

- parallel2会请求两个batch槽，权重共享，各槽独立持有会话状态；需以启动INFO batch_slots和运行状态确认实际生效数量。
- 并发可以改善排队和交错推进，但每槽状态消耗显存，可能压缩专家缓存，单流和聚合吞吐均需测量，不能普遍断言并发绝不提速或必然提高Agent完成速度。
- spec4与MTP路径仅列在核心参数中，不足以证明并发时仍然投机解码。该版本默认batch解码无MTP；batch-mtp需单独启用，并有层分割分组限制。片段未列该选项不等于完整配置必定未启用。
- RAM预算36是配置预算，实际arena/补集大小取决于模式及日志；额外槽的成本包括RAM与VRAM KV、GDN/索引状态、工作缓冲和可选slot drafter。约3.1GB不是跨模型版本固定常量。
- CCD划分是一种线程亲和安排；不能根据这段文字推导本机EPYC/VM拓扑。避免给文本专家线程安排同一物理核的SMT兄弟，与全局关闭超线程不是同一件事。当前本机vision关闭，没有对应CPU编码任务。

## 与本机既有结果的关系

本机此前Swift双客户端补测中，batch聚合吞吐约28.03/28.37 tok/s；parallel1 + pipeline-windows2为34.14/34.81 tok/s（同时/错峰负载）。该负载支持继续采用已选择的pipeline2配置；不代表任意Agent交互流量下的时延或完成时间结论。

parallel控制同时活跃的客户端槽数；pipeline-windows控制层分割内部窗口调度。当前parallel1/pipeline2仍会对第二个客户端排队。

未来如用户需要交互公平性或两个Agent同时输出，应以实际任务完成时间、排队时间、各客户端TTFT和聚合吞吐评估P2，不仅比较面板单请求tok/s。当前保持既定单请求性能诊断计划，不引入并发变量。
