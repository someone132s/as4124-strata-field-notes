# 快捷键、相似案例与理论带宽口径复核

本轮只检索资料和整理已有测量；没有登录主机、运行负载或改配置。

## BIOS 菜单

- Supermicro FAQ 43774（X13DEi）原文是隐藏项需要 OEM BIOS，没有提供解锁快捷键。不能把它作为 H12DSG-O-CPU 有快捷键的证据。
  https://www.supermicro.com/fr-fr/support/faqs/faq.php?faq=43774
- AMI 官方说明 Aptio V 的入口按键可由 OEM 定制；未找到其发布的通用隐藏菜单解锁键。
  https://www.ami.com/resources/top-three-keys-used-to-enter-uefi-bios-setup/
- Ctrl+F1：Acemagic F3A 用户一手报告成功；不是 Supermicro 验证。
  https://www.reddit.com/r/AcemagicOfficials_/comments/1k27xvt/
- Alt+F1：另一 AMD miniPC 用户提到此前与 Alt+F5、重启配合成功，当前复现不明确；不能作为本板标准操作。
  https://www.reddit.com/r/MiniPCs/comments/1glxuga/
- MSI 官方特定 AMD 笔记本组合键：Left Alt + F2 + Right Ctrl + Right Shift；不证明在本板有效。
  https://my.msi.com/faq/faq-12386
- 本板截图 F3 是 Optimized Defaults、F4 是 Save & Exit，不能当作隐藏菜单入口。

## 新增的同型号四 DIMM AIDA64 参照

Diit.cz 2021-07-30 原创评测，Supermicro H12SSW-iN、单 EPYC7282、4×8GB DDR4-3200 Registered ECC CL24-22-22-52 1T。

| AIDA64 | MB/s 或 ns |
|---|---:|
|Read|62917 MB/s|
|Write|42661 MB/s|
|Copy|71586 MB/s|
|Latency|117 ns|

原评测页及同作者后续复用完整图例的数据页（čtení=读取，zápis=写入，kopírování=复制）：
https://diit.cz/clanek/minirecenze-supermicro-1610f-h12w-1u-server/cpu-vykon-ffmpeg-kraken-javascript-7-zip-aida64
https://diit.cz/clanek/test-dell-poweredge-r630-dve-broadwell-ep-ctrnactijadra-v-roce-2021/cpu-vykon-ffmpeg-kraken-javascript-7-zip-aida64

该参照更贴近本机 CPU/四条布局/测试类别，但主板、内存容量、频率和 AIDA64 版本不同，不能计算纯硬件损耗或保证目标值。

## 相似低分案例

2025-04-07，7282 + H12SSL-i、8×32GB Micron 3200 RDIMM，Memtest86+ 报4.89GB/s；四条时4.9GB/s。作者2025-04-10称修改配置并换 MemTest86（非 plus）11.2 后显示13.9GB/s。测试软件和配置一起改变，未证明硬件故障或正常峰值。
https://www.reddit.com/r/servers/comments/1jtvldo/

其中“1GB工作集可以放进单根DIMM，因此只用一条”的评论不能作为解释：交织由地址映射决定，小工作集同样可以跨通道。

未找到 H12DSG-O-CPU + 双7282、同样症状、并已明确定位修复原因的匹配案例。

## 几台机器的比值应怎样解释

- P15 更新为4×16GB=64GB，仍是双通道。DDR4-2133双通道裸峰值34.128GB/s；AIDA Read25.634/Write30.144/Copy26.721分别约75%/88%/78%，不是一半。
- R730 每路两个2133通道理论34.128GB/s，单路LIKWID13.06–15.04约38%–44%。原因尚未分解；不能笼统以“正常效率一半”结案。
- N5105 双通道2667理论42.672GB/s，libc memcpy17.93逻辑GB/s约42%。它是自建Python ctypes调用系统libc、多线程拷贝，统计读取+写入，不是纯读取或标准STREAM峰值。没有控制器实测流量，不能把差额认作内存闲置率，更不能宣布已验证平台峰值。
- STREAM作者区分 bcopy（只算复制的数据量）、STREAM（算读+写）、hardware（实际总线字节）；缓存写分配可能造成额外流量，不能机械套用到纯读取负载，也未证明N5105这轮libc具体使用哪条写路径。
  https://www.cs.virginia.edu/stream/ref.html
- 各测试达到理论接口带宽多少，取决于访存并行度、代码、内存指令开销、地址映射和后台竞争，不存在统一“正常就是50%”。低吞吐可真实复现，不等于已经测到控制器饱和或排除所有测法因素。
