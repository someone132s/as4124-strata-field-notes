# EPYC 7282 低带宽：网上资料复核与下一步诊断

日期：2026-10-16。本轮仅查资料和已有本地记录，没有访问服务器、修改 BIOS、启动测试或停止 VM。

## 目前能下的结论

- 低带宽在 PVE STREAM、LIKWID、控制器计数，以及 PE AIDA64 中重复出现；不是仅凭一个软件截图提出的问题。但不同测试的绝对值不能混作同一指标。
- PVE LIKWID 单路约 7.66/7.10 GB/s，双路约 14.24 GB/s，双路接近两路之和。原有绑定、线程放置和 NUMA 页位置已有检查，不能重新假定从未验证。
- uProf 验证该读取负载确实只产生约 14.7 GB/s 控制器读取；它不能证明硬件已达到极限。每路 C/D/G/H 均有约 1.8–1.9 GB/s 读取，不支持仅一条内存工作的解释。
- 3200 改 Auto（实际 2933）以及 APBDIS=1/P0 对 PE 结果均没有实质改善；前者弱化 DRAM 标称速率是主因，后者弱化 APB 动态状态切换是主因。
- 两路均低且活跃通道均匀，使单根 DIMM/单个通道局部故障的优先级低于共用配置、测试扩展性和平台限制。这是推断，不是排除硬件。

## 本轮新增证据

1. Dell 官方白皮书第 15 页图 10，R6515 单路 EPYC 7282 的 STREAM Triad 报告 81,137 MB/s。网页索引可提取图表标签；网页截图接口未返回可视图像，本地下载被 Dell CDN 拒绝。该数值可作同型号的数量级参照，不能作为本机配置的合格线，不能与 AIDA64 Read 直接相除。
   https://dl.dell.com/manuals/common/poweredge_perf_amdepyc7002series.pdf
2. AMD 型号数据表列 7282 每路理论 85.3 GB/s，并注明四通道 DDR4-2667 优化；不能用泛化八通道型号 204.8 GB/s/路估算它，也不能由其型号较弱解释单路仅数 GB/s。
   https://www.amd.com/content/dam/amd/en/documents/products/epyc/amd-epyc-7002-series-datasheet.pdf
3. AMD 56338 表格列 7282 支持 NPS 1、0。主板通用菜单显示 NPS2/4 不代表本型号支持。
   https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/specifications/56338-socket-sp3-platform-numa-topology-family-17h-models-30h-3fh.pdf
4. Supermicro 实际打开的下载页列 BIOS 3.7/BMC 01.08.08，搜索摘要仍有旧 3.6 信息。用户当前 BIOS 3.6；没有取得说明本次性能问题已修复的发布说明，不能承诺升级有效。
   https://www.supermicro.com/en/support/resources/downloadcenter/firmware/MBD-H12DSG-O-CPU/BMC
5. 本地 as4124/independent/edac-inventory.json 内容是 []。空采集不是 CE/UE=0，需核实驱动/接口和 BMC SEL。Linux EDAC 文档说明可纠正错误发生时系统仍可正常运行，因此长期稳定不等于无硬件错误。
   https://www.kernel.org/doc/html/latest/admin-guide/RAS/main.html
6. Rome 实测论文明确比较核心/CCX/CCD 分布对带宽饱和的影响，并控制数据放置、预取和频率。该论文 CPU 是 7702，不可把其数值当 7282 标准。
   https://arxiv.org/html/2204.03290v1
7. AMD 的 APBDIS=1/P0 建议确有出处，作用是固定高性能 Fabric 状态、避免状态切换延迟；本机对照没有收益，并不等于所有功率/温控限制已排除。
   https://docs.amd.com/api/khub/documents/cfE3LuUQtmpHZxHm15xDyA/content
8. AMD 当前 E-SMI 主分支硬件支持表从 Zen3 起，不应直接承诺在 Zen2 7282 上用最新版 E-SMI 读取所有 Fabric/内存指标。无法读取的项目应明确记为未知，不能拿 UCLK 代替 FCLK。
   https://github.com/amd/esmi_ib_library

## 下一轮最小诊断矩阵（尚未执行）

前提：安排业务空闲窗口；PVE 宿主无 VM 负载，或使用干净 Linux Live。不为这轮同时更改 BIOS。保留当前 DIMM 布局及配置记录。

1. 先检查已有 BMC SEL、CPU/DIMM/VRM 温度、电源/功率限制信息和内核 RAS/MCE/EDAC 记录。测试前后取错误计数增量。接口缺失记未知。
2. 复用已验证 LIKWID load_avx，数组固定并显著大于 LLC；逐路测 1/2/4/8/16 个物理核心，记录 CPU 时间、有效频率、工作核心、内存位置、控制器流量。少核心另比较同 CCD 与分散 CCD 放置。
3. 对每个 CPU 节点分别访问两路内存，组成 0→0、0→1、1→0、1→1 矩阵；带宽和依赖指针追逐延迟分开测。用实际页位置及 xGMI 流量核实本地/跨路，不只看 numactl 命令。
4. 若本地单路明显正常而跨路低，优先 xGMI/放置；若两路本地都低，优先共享平台状态或请求并行度。若少量核心即达到同样低平台，看共享路径；若随核心近线性但每核均低，看每核有效运行、预取及代码路径。
5. 两路本地仍低时，以同一二进制/参数比较干净 Linux Live 与 PVE，隔离内核、后台负载和宿主环境。PE 与 Linux 是跨 OS、跨工具对照，不能替代该单变量比较。
6. 根据曲线才决定补充只读/非临时写/预取或页大小对照、核实固件默认值。需要更新固件时先取得对应修复说明及厂商建议，保留基线，每次只改一个因素。
7. 出现特定通道错误或一侧显著异常后，才做保持有效布局的 DIMM/已知良品交换：异常跟 DIMM 走偏向 DIMM，留在插槽/CPU 一侧偏向主板/CPU 内存控制器，均需后续隔离。当前两路同样慢时整组左右交换的鉴别力有限。

不把通用 MemTest 长时间通过当作带宽正常的证据；也不凭目前结果建议立即购买内存或更换 CPU。
