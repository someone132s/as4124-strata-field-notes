# AS4124：用户加载 Optimized Defaults 后的截图记录

来源：用户于2026-10-16提供的 iKVM_capture (48)–(66).jpg，共19张。用户明确称这组为机器自带默认配置。截图证明界面中的配置值；尚未收到保存重启后的PE跑分，也不能仅凭内存信息页证明已经按新设置重新训练。

原配置另存 AS4124-BIOS-回退清单-20261016-before-defaults.md，本文件不覆盖原值。

## 已知差异

|页面/项目|恢复前最后记录|默认截图|来源|
|---|---|---|---|
|CPU / Global C-state Control|Enabled|Auto|53|
|CPU / Local APIC Mode|x2APIC|Auto|53|
|NB / IOMMU|Enabled|Auto|54|
|NB / APBDIS|1|Auto|54|
|NB / Fixed SOC Pstate|P0|未显示|54|
|NB / DF Cstates|Enabled|Auto|54|
|ACPI / PCI AER Support|Enabled|Disabled|51|
|NB / ACS Enable|Auto|未显示，不记为Disabled|54；当前AER为Disabled|
|Memory / DDR Power Down Enable|Enabled|Auto|56|
|PCIe / Re-Size BAR Support|Enabled（此前核对记录，未在CPU交换后重拍）|Disabled|59|
|PCIe / ASPM Support|Auto（此前核对记录）|Disabled|59|

Auto不等于Disabled；未显示不等于Disabled。ACS显隐与AER相关符合此前板厂FAQ，但截图不能给出隐藏后的实际ACS值。Fixed SOC Pstate在APBDIS Auto下未显示，不能据此认定运行在P0或其他固定状态。

## CPU Configuration（53）

SMT Control、Core Performance Boost、Global C-state Control、Local APIC Mode、CCD Control、Core Control、L1 Stream HW Prefetcher、L2 Stream HW Prefetcher、SEV ASID Count、SEV-ES ASID Space Limit Control均为Auto。SVM Mode=Enabled。

## NB / xGMI / Memory（54–56）

NB：Determinism Control、cTDP Control、IOMMU、Package Power Limit Control、APBDIS、DF Cstates、Preferred IO均为Auto。

xGMI Link Width Control、xGMI Link Max Speed均为Auto。

Memory Clock、Memory interleaving、Memory interleaving size、Chipselect Interleaving、BankGroupSwap、DRAM Scrub Time、TSME、DDR Power Down Enable全部Auto。

CPU1/CPU2 Memory Information（57–58）：每路C2/D2/G2/H2各32768MB，显示2933 MT/s；其余槽Not Present。共8条、256GB、两路各128GB，截图未显示丢失DIMM。频率信息可能对应进入Setup前的训练状态，保存重启后的实际值待PE确认。

## ACPI（51）

PCI AER Support=Disabled；High Precision Event Timer=Enabled；NUMA Nodes Per Socket=Auto；ACPI SRAT L3 Cache As NUMA Domain=Auto。

## PCIe（59–60）

|项目|默认截图值|
|---|---|
|PCI Bus Driver Version|A5.01.19（信息）|
|Above 4G Decoding|Enabled|
|Re-Size BAR Support|Disabled|
|SR-IOV Support|Enabled|
|BME DMA Mitigation|Disabled|
|ASPM Support|Disabled|
|ARI Support|Auto|
|PCIe Ten Bit Tag Support|Auto|
|PCIe Spread Spectrum|Disabled|
|Relaxed Ordering|Enabled|
|No Snoop|Enabled|
|VGA Priority|Onboard|
|NVMe Firmware Source|Vendor Defined Firmware|
|SLOT1–SLOT10 PCI-E 4.0 X16 OPROM|均EFI|
|Onboard SAS Option ROM|EFI|
|Onboard LAN|Enabled|
|Onboard LAN1 Option ROM|EFI|
|Onboard NVMe1–NVMe4 Option ROM|均EFI|
|Onboard Video Option ROM|EFI|
|JS1A/JS1B–JS10A/JS10B Bifurcation|均Auto|

原配置未记录的PCIe细项，不能将本组默认值回填为原值。

## 其余页面

- Boot Feature（48）：Quiet Boot=Enabled；Option ROM Messages=Force BIOS；Bootup NumLock State=On；Wait For F1 If Error=Disabled；INT19 Trap Response=Immediate；Re-try Boot=Disabled；Watch Dog Function=Disabled；Restore on AC Power Loss=Last State；Power Button Function=Instant Off。与补充原配置43一致。
- Trusted Computing（49）：Security Device Support=Enabled；NO Security Device Found。与原44一致。
- PSP（50）：Level1 Recovery BL FF.C.0.8C；Level2 BootLoader 0.C.0.8C；两级SMU 0.36.119.0、ABL 52102010。与原45一致，均为只读版本信息。
- Serial Port Console Redirection（52）：COM1重定向Disabled；SOL重定向Enabled；Legacy Serial Redirection Port=COM1；EMS重定向Disabled。各子菜单未展开，旧值未记录。
- USB（61）：Legacy USB Support=Enabled；XHCI Hand-off=Enabled；Port 60/64 Emulation=Enabled。USB Module Version24；7 XHCIs；2 Drives/3 Keyboards/2 Mice/3 Hubs为当时设备信息。旧值未记录。
- Network Stack（62）：Network Stack=Enabled；IPv4/IPv6 PXE Support=Enabled；IPv4/IPv6 HTTP Support=Disabled；PXE Boot Wait Time=0；Media Detect Count=1。网络接口子菜单未展开，旧值未记录。
- SATA（63）：SATA Enable=Auto；SATA Hotplug=Enabled；SATA Information子菜单未展开。没有显示AHCI/RAID模式，不能自行补填；旧值未记录。
- HTTP Boot（64）：HTTP Boot Policy=Apply to each LAN；HTTPS Boot Checks Hostname=Enabled；Priority1 Instance=1，IPv4，Boot Description/Boot URI空；Priority2 Instance=0。旧值未记录。
- Security（65）：System Mode=User；Secure Boot状态Not Active、开关Disabled；Secure Boot Mode=Custom；CSM Support=Enabled。与原46一致；密钥管理未展开。
- Boot（66）：Boot Mode Select=UEFI；LEGACY to EFI Support=Disabled。优先级与原47一致：UEFI Hard Disk、UEFI CD/DVD、UEFI USB Hard Disk、UEFI USB CD/DVD、UEFI USB Key/SanDisk Partition2、UEFI USB Floppy、UEFI USB Lan、Intel I350 IPv4 PXE、Built-in EFI Shell。未展示硬盘类别内部具体引导项。

## 下一步性能对照

保持八条内存原位，保存本组设置并重启进入同一PE，AIDA64测两次，记录实际容量/内存频率及Read、Write、Copy、Latency。

恢复前APBDIS1/P0+Memory Auto的PE两次均值：读取17187.5、写入19969.5、复制17424 MB/s、延迟167.6ns。默认后的结果尚未提供。默认值对照期间先保持当前Auto/Disabled项目，不加回原调优，以便观察整组厂商默认状态是否改变低吞吐。

## 默认配置保存重启后的PE结果（补充截图67–69）

截图67的AIDA64 Business8.30.8300 / BenchDLL4.7.929.8-x64：读取17233 MB/s，写入20077 MB/s，复制17466 MB/s，延迟167.3ns。目前只有一组完整成绩；截图68–69背景为同一组结果，不计作独立重复。

相对恢复前两次均值：Read +0.26%，Write +0.54%，Copy +0.24%，Latency -0.3ns，未见实质改善。支持“本次恢复厂商默认未解决低吞吐”，不证明固件/初始化/内存兼容性已排除。

HWiNFO截图68：所选P1-DIMMC2、32GB，MCLK1466.7 MHz，UCLK733.3 MHz，Channels4；23-21-21-47 CR1。频率及时序仍处于原水平。CPU在AIDA中约3200.1MHz。

### 型号需要纠正的线索

用户称全部内存型号相同，但截图69的八项下拉列表可读为：DB2、DB2、CB2、CB2、DB2、DB2、CB2、CB2；完整字符串分别为Samsung M393A4K40DB2-CVF与Samsung M393A4K40CB2-CVF。按界面暂计各四条，待逐条SPD/实体标签确认。

这证明截图所报告型号字符串并非完全相同，尚不证明物理标签差异、混插不兼容或带宽根因；列表顺序不作为槽位映射。建议拆装前逐条记录槽位、完整型号、序列号及标签；先原位重插；后续按型号分组进行保持CPU、槽位、数量、固件设置相同的互换对照。每CPU两条的减半配置仍需先核对支持布局。
