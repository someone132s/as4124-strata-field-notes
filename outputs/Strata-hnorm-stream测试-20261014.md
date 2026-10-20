# hnorm stream 与显存预留短测（2026-10-14）

用户授权暂停正式评测，应用 `--mtp-hnorm stream`、主卡预留550MiB、后续卡预留600MiB；先执行既定课本短测，再单独运行Strata官方性能套件。日期与时间均按北京时间。

## 正式评测暂停

- 已完成的IQ3 C-Eval80题、MMLU-Pro60题保持不变。
- 当前IFBench已落盘44条预测保留；未完成请求没有当作有效答案或质量失败计入统计。
- 当前job停止；campaign状态为`paused` / `paused_by_user`，小时自动任务`evalscope`为`PAUSED`。
- 原脚本已有`use_cache`续跑路径。本次未恢复评测；恢复前需决定恢复原引擎配置，还是明确记录配置变更边界，不能默默混合两种设置。
- 暂停记录：测试VM `/opt/evalscope/outputs/campaigns/iq3-vs-udiq4-20261014/pause-request.json`。systemd原任务因停止返回非零，其状态已留档并reset-failed，最终两个评测unit均为inactive。

## 配置与验收

镜像及模型不变：引擎0.1.43.1、Swift IQ3_S + Q8 PLE、纯文本、256K、15 workers、2槽、groups1+batch-mtp、BF16_TC1、STAGE_TRIM1、int8 KV resident32768、auto分层。

本次仅修改三个显式参数，已从运行中进程argv核对：

```text
--mtp-hnorm stream
--vram-reserve-mib 550
--vram-reserve-later-mib 600
```

配置路径：`/opt/strata-data/config/strata-swift-iq3_s-q8ple.json`。

变更前备份：`/opt/strata-deploy/backups/codex-hnorm-stream-20261014-232206/`，含原配置、Compose及启用后的配置。

启动结果：auto仍为25/23；专家槽16391→16522（+131），专家缓存31829→32164MiB（+335MiB）。锁页专家补集为22.75GiB，prefill借槽3857个全部保留RAM副本，ring96、chunk8192。

## 课本短测

两个不同预热问题，之后三个正式问题；预热不计入统计。每次带唯一编号，所有正式请求`reused=0`。不保存请求/回答正文。

| 阶段 | questions文件题号 | 内容 | 输出上限 |
|---|---:|---|---:|
| 预热1 | 1 | 主要内容 | 512 |
| 预热2 | 2 | 切口设计 | 512 |
| 正式1 | 3 | 询问病史 | 1024 |
| 正式2 | 6 | 口腔检查 | 1024 |
| 正式3 | 5 | 记录病历 | 1024 |

temperature0、top_p0.95、top_k20、seed20261014、reasoning none。输入约19686 token，完整重新读入。

| 正式题 | 输出token | 后端decode tok/s | 客户端TTFT s | 整请求墙钟 s | 专家命中率 |
|---|---:|---:|---:|---:|---:|
| 病史 | 1024 | 60.1 | 15.47 | 32.50 | 98.1% |
| 口腔检查 | 1024 | 66.3 | 15.78 | 31.21 | 98.5% |
| 病历 | 1024 | 61.3 | 16.35 | 33.02 | 98.5% |

汇总：后端decode中位数 **61.3 tok/s**；prefill加权 **1248.17 tok/s**；TTFT中位数 **15.78s**；串行整批端到端输出吞吐 **31.76 tok/s**。三题均达到输出上限，`finish_reason=length`，属于定长速度测试，不评价答案完整性或质量。MTP共提议2578、接受2060，约79.9%。

采样最低空闲显存：GPU0 **134MiB**，GPU1 **82MiB**。短测后容器OOMKilled=false、RestartCount=0。显存预留不是实际剩余显存保证；本次仅验证串行约20K输入，不能外推到256K或其他双并发峰值。官方两客户端测试单独记录。

历史18:11纯文本短测decode中位数49.2，本次61.3，数值约高24.6%；但历史输出上限512，本次1024，预热不同，且本次同时改变hnorm与预留，**不将其认定为hnorm独立提速24.6%**。本次未运行关闭hnorm的对照臂，遵循用户“只测启用”要求。

原始数据：[hnorm-stream JSON](remote-results/hnorm-stream-20261014-232206.json)。脚本：[本次脚本](../work/test_hnorm_stream.py)。

## 官方benchmark

用户指定后续性能测试优先采用官方 `tools/strata_bench.py`。该套件是性能测试，与EvalScope模型质量评测分开。

本次使用服务器现有源码中的脚本，连接已运行服务，不启动另一个模型、不更换配置：

```bash
python3 -u tools/strata_bench.py \
  --url http://10.2.21.4:8080 \
  --config /opt/strata-data/config/strata-swift-iq3_s-q8ple.json \
  --runs 3 --clients 2 \
  --out /opt/strata-deploy/test/results/official-hnorm-stream-20261014
```

标准内容：短聊天、约4K/16K fresh prompt、agent会话缓存测试（每会话初始轮加五个后续轮），以及本次附加的两客户端并发。未启用`--think`或`--long`。官方agent session主要测会话性能和缓存，并非完整agent任务质量benchmark。

执行unit：`strata-official-bench-20261014-hnorm.service`，最终Result=success、ActiveState=inactive；套件耗时 **210.03秒**，failures为空、skipped为空，并发错误0。其预热由官方脚本自行执行，与上方课本短测分开统计。

| 指标 | 中位数 | 范围 / 样本 |
|---|---:|---|
| 短聊天decode | 43.6 tok/s | 28.7–56.1，9请求，每题最多100输出token |
| 短聊天TTFT | 0.751s | 约0.594–1.292，9请求 |
| 4K prefill | 803.0 tok/s | 788.6–819.1，3请求，实际4019输入token且未复用 |
| 4K TTFT | 5.077s | 4.972–5.166 |
| 16K prefill | 1251.0 tok/s | 1248.1–1270.8，3请求，实际16058输入token且未复用 |
| 16K TTFT | 12.963s | 12.772–12.982 |
| Agent后续轮decode | 56.8 tok/s | 19.3–79.1，15个后续轮 |
| Agent后续轮TTFT | 约4.40s | 3.15–5.38 |
| Agent缓存命中（官方口径） | 68.63% | 68.48–68.81%，3会话 |
| Agent旧token重读/会话 | 75 | 4–145，3会话 |
| 两客户端端到端总吞吐 | 37.56 tok/s | 23.82、37.56、41.27，3轮，每轮共256输出token |

两客户端请求TTFT p50/p95=1.490/2.581s，请求总时延p50/p95=6.717/10.714s。这里只有6个并发请求，分位数不代表高负载长期延迟分布。官方短聊天与并发各轮有明显波动，不把单次峰值当稳定速度；也不将官方短任务吞吐与课本1024输出decode相除。

官方报告：[README](remote-results/official-hnorm-stream-20261014/2026-10-14-community-2x-rtx-2080-ti-swift-1-5-abliterated-iq3-s-q8ple/README.md)、[逐请求JSON](remote-results/official-hnorm-stream-20261014/2026-10-14-community-2x-rtx-2080-ti-swift-1-5-abliterated-iq3-s-q8ple/results.json)。报告在GPU VM上采集机器信息，CPU/RAM是VM可见信息，宿主硬件背景应结合总记录理解。

脚本来自当前安装源码commit `a0116b2782a5b82622358c04a06496485d12b2d6`，SHA256=`ca4c4bb7fea4a2e7469bfc0925f41ad8584491a1c054b144a323b9767a495dafd`，没有修改官方脚本。说明见[官方社区基准指南](https://github.com/Niko1221/Strata/blob/v0.1.43.1/docs/COMMUNITY_BENCHMARKS.md)。

## 最终状态

两套测试全部完成，服务健康、idle、无排队，仍是IQ3纯文本/256K/2槽位。保留stream与550/600MiB预留；本次重启后日志未检出CUDA allocation/OOM/non-finite错误，容器OOMKilled=false、RestartCount=0。短测试通过不等于已覆盖256K上限或视觉负载。

正式评测与小时自动推进保持暂停，没有切换UD-IQ4，也没有自动恢复IFBench。

配置快照：[新配置](Strata调优资料-20261014/IQ3-hnorm-stream-550-600配置.json)；验收：[最终状态](remote-results/hnorm-final-state-20261014.json)、[启动证据](remote-results/hnorm-stream-startup-20261014.txt)。
