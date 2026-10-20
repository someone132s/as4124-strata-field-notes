# AS4124 PE / AIDA64 实测（2026-10-16）

来源：用户提供两张 AIDA64 Business 8.30.8300 / BenchDLL 4.7.929.8-x64 完整结果截图，以及 HWiNFO64 8.55-6095 内存时序截图。

| 次数 | Read MB/s | Write MB/s | Copy MB/s | Latency ns |
|---|---:|---:|---:|---:|
| 1 | 17327 | 19975 | 17478 | 167.6 |
| 2 | 17239 | 20006 | 17437 | 167.6 |
| 均值 | 17283 | 19990.5 | 17457.5 | 167.6 |

两轮差异相对均值：Read 0.51%、Write 0.16%、Copy 0.23%。无第三轮数据。

## Memory Clock Auto 保存重启后的对照

用户新截图：Read 17257 MB/s、Write 20033 MB/s、Copy 17446 MB/s、Latency 167.4 ns。
内存实际变为 DDR4-2933R，23-21-21-47 CR1；MCLK 1466.7 MHz、UCLK 733.3 MHz。
与原3200两轮均值比较，Read -0.15%、Write +0.21%、Copy -0.07%，延迟 -0.2ns。降频已生效，但本轮无实质改善，降低“强制3200导致主要性能异常”的嫌疑；不能据此声称根因已定位或所有频率因素均已排除。当前只有一张Auto跑分结果。

## APBDIS=1 / Fixed SOC Pstate=P0 对照

用户在BIOS截图确认选定APBDIS1与P0，随后重启PE提供两次结果：

| 次数 | Read MB/s | Write MB/s | Copy MB/s | Latency ns |
|---|---:|---:|---:|---:|
| 1（capture40） | 17188 | 19966 | 17405 | 167.6 |
| 2（capture41） | 17187 | 19973 | 17443 | 167.6 |
| 均值 | 17187.5 | 19969.5 | 17424 | 167.6 |

HWiNFO（capture42）：MCLK1466.7、UCLK733.3MHz，与Auto基线一致。相对Auto单次基线，Read-0.40%、Write-0.32%、Copy-0.13%，延迟+0.2ns，没有实质改善。不把UCLK未变解释为APBDIS未生效，因为UCLK不是FCLK；尚未独立读取运行时Fabric Pstate。

识别信息：2×16-Core AMD EPYC 7282，CPU 3200 MHz；Quad Channel DDR4-3200R，24-22-22-52 CR1；Memory Bus 1600 MHz；BIOS 3.6 / AGESA RomePI-SP3 1.0.0.P。HWiNFO 显示 Supermicro H12DSG-O-CPU，所选 Samsung M393A4K40DB2-CVF、32GB、P1-DIMMC2，MCLK 1600 MHz、UCLK 800 MHz、Channels 4。所选 DIMM 视图不代表已逐一确认两路所有控制器。

结论：不运行 PVE/VM 的独立 PE 环境仍测得十几 GB/s，削弱“仅由 PVE、VM 背景争用或 Linux 基准封装造成低数值”的解释；尚不能判定硬件故障，也未证明任一基准已经达到双路硬件最大带宽。AIDA64 未提供本轮线程/NUMA 页面落点，因此不将结果直接视为两路各自饱和带宽之和。

MCLK 1600 与 DDR4-3200 一致，强制 3200 的设置有运行时报告支持。UCLK 800 是待验证线索，不等于已测得 FCLK 800，也不能直接把桌面 Ryzen 的同步规则套给 EPYC 7282；截图无法确认负载时频率。

后续受控对照：记录现有 BIOS 项，首先只把 Memory Clock 从 3200 改 Auto，保持其余设置，重新 PE 测两次并记录实际 MCLK/UCLK；若无显著改变，再逐项核对内存交织/插槽分布、Fabric 电源策略与本地/跨路内存访问。不要一次重置全部 BIOS、同时改多项或直接强制 UCLK/FCLK。

参考：
- AMD EPYC 7282 官方规格：每路带宽列 85.3 GB/s，最高 DDR4-3200；不能套用通用 Rome 每路 204.8 GB/s。
  https://www.amd.com/en/support/downloads/drivers.html/processors/epyc/epyc-7002-series/amd-epyc-7282.html
- AIDA64 官方基准说明：多线程支持 SMP；支持多 CPU 不证明某次测试所有内存节点均饱和。
  https://www.aida64.com/user-manual/benchmarks
