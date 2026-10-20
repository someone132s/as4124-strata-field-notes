# Strata 0.1.45 升级记录

目标机器：VM502 / gpuserver1，10.2.21.4。升级前为 0.1.43.1；本次固定官方 v0.1.45 提交 `477ac13cbe8e582c20484871ce459d20d82df09d`，CUDA 架构为 SM75。

## 配置范围

- 开启 `STRATA_SM75_PERF=1`、`STRATA_PA_V2T=1`；保留 `STRATA_BF16_TC=1`。
- 保持 SC117 IQ3_S 模型、Q8 PLE 表、15 workers、262144 上下文，以及原有专家缓存和 MTP 配置。
- 两张 2080 Ti 负责推理；2070 SUPER 专门处理视觉，视觉上限 16384 token。显卡按 UUID 指定。
- `STRATA_ROUTE_PRIOR` 保持未开启。这次不同时改变专家选择策略。
- 接口地址保持 `http://10.2.21.4:8080/v1`；模型名保持 `sc117-qwen3.8-flash-next-abliterated-iq3_s-q8ple`。

## 构建与恢复

独立源码目录 `/opt/strata-deploy/source-v0.1.45`，镜像 `strata:vm502-v0.1.45-sm75-vision-gpu`，镜像 ID `sha256:68bf77f20c165ae3b64d9c329e76649da238786e85b56f6135b626e391bac5e7`。复用既有 CUDA 工具链与固定版本 llama.cpp，重新编译引擎、GPU 视觉编码器和内核校验程序；初始构建并行数为 2，视觉构建后半程在确认约 40GB 可用内存后调整为 8。构建期间保留旧服务运行。

已验证镜像内 `libstrata_kq.so` 与构建产物 SHA256 一致：`d71df16f030fe8b5215c771607d221f253e729dcd2de09e4939db7c43cb41306`。Python 依赖检查通过。

切换前备份 compose 和配置，并为旧镜像创建 rollback 标签。自动部署程序在内核或接口检查失败时恢复旧配置与旧服务。本次验证全部通过，没有触发回退。

- 备份目录：`/opt/strata-deploy/backups/upgrade-v0145-20261017-194802/`
- 旧镜像保留标签：`strata:rollback-20261017-194802`
- 当前配置：`/opt/strata-data/config/strata-sc117-iq3_s-q8ple-vision-v0.1.45.json`
- 当前服务日志：`/opt/strata-data/logs/strata-sc117-q8-v0.1.45-sm75.log`

## 验证状态

2026-10-17 19:54（北京时间）全部通过。完整结果见同目录 `Strata-0.1.45升级验证-20261017.json`；远端原件位于 `/opt/strata-deploy/test/results/upgrade-v0145-20261017.json`。

| 检查 | 结果 |
| --- | --- |
| `mmvq_il_parity` | 通过 |
| `native_grouped_parity` | 通过 |
| `qsa_prompt_attn_parity 8192 256 1`，开启两个新开关 | 通过 |
| Chat Completions 文本计算 | 正确返回 42 |
| 38514 token 长输入 | 正确返回目标颜色；输入缓存为 0 |
| Responses 普通接口 | completed |
| Responses SSE 流式接口 | HTTP 200，收到 response.completed，无 error |
| 512×512 图片 | 识别正确，实际视觉 token 为 256 |
| 4096×4096 图片 | 识别正确，实际视觉 token 为 16384 |
| 运行进程环境 | SM75_PERF=1、PA_V2T=1、BF16_TC=1；ROUTE_PRIOR 未设置 |
| GPU 分工 | 2070S 运行 strata-vision；两张 2080Ti 运行 strata |
| 最终状态 | version 0.1.45，health ok，已加载，idle，无排队；容器无 OOM、无重启 |

长文本这一次的预填充记录为 1855.9 token/s；大图请求总耗时约 126.5 秒，其中引擎预填充约 11.2 秒。两项均为合成功能检查，不能直接代表实际业务速度。短输出只有 2–3 token，也不足以评估稳态 decode 性能。本次没有进行旧版与新版的严格 A/B 测试，实际收益由后续相同输入的使用或对照测试判断。

官方版本：[v0.1.45](https://github.com/Niko1221/Strata/releases/tag/v0.1.45)。
