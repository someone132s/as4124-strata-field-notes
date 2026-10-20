# Hanayo RTX3090 调优文章：核对与本机应用

原文：https://hanayo.cn/2026/10/14/strata-3090-tuning/
本地阅读快照：hanayo-3090.html / hanayo-3090.txt。
公开CSV副本：hanayo-prefill-ablation.csv、hanayo-prefill-memory.csv、hanayo-bottleneck-observations.csv。
固定版本源码阅读副本：hanayo-source-prefill.cpp，commit7695859aa13afb248bdb4d36f9b2e95707db079d。

## 核对结果

文章平台是单RTX3090、Gold5318Y的16vCPU、32GB RAM Linux VM、IQ2_XS、32K配置窗口。不能直接代表本机双2080Ti、128GiB、Swift IQ3_S、262144窗口。

CSV复算：40行含16次warmup和24次measured；正式四组各6次，均reused_tokens=0、fields_correct=5、io_MB=0。

| chunk / CPU share | TTFT均值(s) | prefill均值(tok/s) |
|---|---:|---:|
| 256 / auto | 13.2815 | 335.0167 |
| 256 / off | 16.1133 | 291.7167 |
| 1024 / off | 6.1358 | 743.9667 |
| 2048 / off | 3.5422 | 1253.8167 |

文章的正反序与完整输入预热让这组证据比单次峰值更可靠，但只有一份4392token结构化输入，不能外推256K最优chunk。

源码核对：prefill.cpp的stream_all_min默认1024；单卡CUDA符合条件时默认允许小块CPU share，达到阈值使用stream-all路径。该默认CPU share不用于layer split/batch/HIP。阈值判断当前实际块长度，环境变量可覆盖；不能直接将单卡默认规则套到双卡。

## 对本机的启示

- KV前缀复用为0，与专家/PLE/文件页缓存未预热是两个不同条件。既定测试应明确：已预热权重/PLE，正式请求KV复用0。
- decode专家高命中或专家file reads为0，不能排除PLE等待，也不能代表prefill阶段的驻留情况；需按请求对齐read_bytes、major faults、引擎prompt时间、GPU活动及数据路径。
- 仅看GPU利用率接近100%无法区分计算、搬运与等待。CPU累计秒数是多线程求和，不等同于请求墙钟时长；少用CPU也不保证更快。
- 本机当前PLE=ram。若已真正加载/锁页且请求间没有实际读盘，文章的PLE mmap缺页主因就不能照搬。应验证实际状态，不只看参数。
- chunk会临时借出显存专家槽，RAM要保留对应备份；prefill结束回填后，decode缓存容量可恢复，因此decode高命中不能排除prefill借槽的成本。
- 本机pool-workers15、32vCPU、aux-cpus auto已启用。不能照搬该文7workers；后续如需对照，先核对实际亲和与NUMA，再决定是否减少线程。
- 尾部跳过关闭已在本机配置中，保持质量评测设置不变；少数修复题的1/2和0/2不能建立总体质量差异。
- VM环境本身不足以判定性能损失，需看NUMA、CPU调度和数据路径。

保持已讨论的内存带宽→Swift IQ3配对长输入安排。本次仅下载公开阅读资料并复核CSV/源码，没有运行服务器测试、更换模型或修改参数。
