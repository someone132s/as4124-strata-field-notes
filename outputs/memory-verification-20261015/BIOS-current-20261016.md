# AS4124 当前 BIOS 截图核对

来源：用户提供 iKVM_capture.jpg 与 (1)–(36)，2026-10-16，在 BIOS 内将 Memory Clock 从 3200 改为 Auto，尚未提供保存重启后的测试。

- 主板 H12DSG-O-CPU，BIOS 3.6，Build 03/04/2026，CPLD F0.A4.45，256GB。
- CPU1/CPU2 都为 EPYC 7282、16C32T、微码 830107D；BIOS 页显示 2800MHz。
- 每路 C2/D2/G2/H2 各 32768MB，其余空，合计每路128GB。两路信息均显示3200MT/s，这是当前开机已训练状态；不能证明尚未保存重启的 Auto 也会训练3200。
- SMT/Core Performance Boost/CCD/Core/L1、L2 Stream HW Prefetcher 为 Auto；Global C-state Enabled，x2APIC，SVM Enabled。
- NUMA Nodes Per Socket Auto；ACPI SRAT L3 Cache As NUMA Domain Auto。
- NB：Determinism/cTDP/Package Power Limit Auto；APBDIS 0；DF Cstates Enabled；IOMMU Enabled；ACS/PreferredIO Auto。
- xGMI Width/Max Speed Auto；未提供 Width 下拉帮助。
- Memory Clock 已选 Auto；Memory Interleaving、Size、Chipselect、BankGroupSwap、Scrub、TSME 都为 Auto；DDR Power Down Enabled。
- 当前固件 Memory Interleaving 下拉只有 Disabled/Auto，不应按旧手册强求 Enabled 项。
- PCIe：Above4G/ReBAR/SRIOV Enabled；ASPM Auto；SpreadSpectrum Disabled；RelaxedOrdering/NoSnoop Enabled。

判断：未见丢失容量、两路容量不对称、显式关闭交织或预取器的证据。APBDIS/DF/DDR省电设置是后续受控对照候选，尚无因果证据。TSME Auto 不等于运行时已启用。C2/D2/G2/H2 不能单凭“2”后缀判定错槽，主板手册确实优先使用带2后缀的槽；每路四条的最佳通道组合仍需结合该CPU和OEM人口规则核实。

补充截图只需 APBDIS 当前值/下拉/帮助，以及 NPS 下拉/帮助；若有余力再看 xGMI Width。先不更改这些项目。下一轮只保存 Memory Clock Auto 并回PE复测。

主板手册：https://www.supermicro.com/manuals/motherboard/EPYC7000/MNL-2299.pdf
