# 小登步入中登：7900 XTX / Windows / IQ3_XXS 六图案例

来源：用户2026-10-15提供的正文和同组六图；小红书作者“小登步入中登”。只有资料阅读与核对，无服务器配置变更或性能测试。

## 作者报告

RX7900XTX24GB、64GB DDR5、Windows原生HIP预编译Strata0.1.43.1、GSQ-RCO IQ3_XXS；未给CPU型号、内存频率/通道、专家槽数、完整请求与日志、重复次数。与前一组双E5 Linux7900XTX案例分开记录。

参数片段：max-context262144、kv int8/resident32768、expert-cache auto、prefill auto、spec4、mtp（路径省略）、spec-min-p0.70、pcie-frac0.20、vram-reserve-mib2048；启用gfx1100 hipBLASLt表（未给具体版本/文件）。

| 标称prompt tokens | prefill(tok/s) | TTFT(s) |
|---:|---:|---:|
| 10000 | 1596 | 6.7 |
| 17000 | 1618 | 10.2 |
| 43000 | 1626 | 26.5 |
| 52000 | 1594 | 32.4 |
| 136000 | 1498 | 90.9 |

输入数取图中近似值，不推导精确计时误差。decode作者报告：日常87–93；代码99/接受率86%；创作79/接受率74%。没有配对相同输出、相同接受率下的硬件对照。

## 判断与边界

- 曲线主要呈平台，后段略降，增加了一个“长输入不持续上升仍可能正常”的观察。不能将本机平台形状本身当作故障；绝对差距仍需同负载核对。
- 实际表格最长约136K，262144是配置上限；尚不能证明已跑过接近256K输入及其质量。
- “冷启动”未定义：可能仅KV复用0，也可能引擎新启动，不能推出OS/专家/PLE缓存均冷。
- IQ3_XXS与本机SwiftIQ3_S、GPU架构与后端均不同；64GB DDR5不能代替CPU/带宽证据。
- 13.7KB/token可作该官方KV配置的估算，128Ki增加到256Ki约增加1.8GB（约1.7GiB）。它不等于总进程内存增长，亦不保证64GB任意模型可用。若实际需求45GB，单减上下文不足以解释32GB能装下，需同时调整专家/PLE模式等。
- 固定版本AMD_HIP.md的Windows段明确写no calibration，与帖子“Windows AMD可用calibrate”冲突；先按待核实记录，需作者入口、日志或补丁版本，不据此安排自动校准。文档同时写该Windows视觉路径未支持，不能保证单独编译一个vision程序即可贯通。
- HIP调优表要匹配GPU架构、hipBLASLt版本和矩阵形状，不用于本机CUDA。pcie/spec组合、显存预留2048不作为通用最佳值。

## 官方核对

https://github.com/Niko1221/Strata/blob/v0.1.43.1/docs/AMD_HIP.md
https://github.com/Niko1221/Strata/blob/v0.1.43.1/docs/DETAILS.md

本机仍按已讨论的内存带宽与Swift配对负载方案推进；该案例暂未提供新的必须立即启用的参数。
