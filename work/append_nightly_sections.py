#!/usr/bin/env python3
"""Append the 2026-10-20 follow-up sections to three field-study HTML documents."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
SECTION_ID = "nightly-20261020"

PLATFORM = r"""
<section class="chapter" id="nightly-20261020">
<header class="chapter-head"><span class="section-number">FOLLOW-UP / 2026-10-20</span><h2>补测：换回 7282 后，严重低带宽没有重现</h2><p class="subtitle">2026-10-20 11:08–11:12，Asia/Shanghai</p></header>
<div class="stage-config"><b>当前条件</b><span>2× AMD EPYC 7282，64 个逻辑 CPU，约 256GB 内存；四路电源均为 ok；8 台虚拟机保持运行。测试期间 boot ID 未变化。</span><small>这不是隔离负载的极限测试；AER corrected 事件仍在。</small></div>
<p>用户把 7452 换回 7282 并重启后，先跑 LIKWID 纯读取，再跑 STREAM。第一轮节点 0 的读取有超过一半页面实际落在节点 1，不能当作本地带宽；第二轮用 <code>numactl --membind</code> 严格绑定，并核对页落点。</p>
<div class="table-scroll"><table><thead><tr><th>配置</th><th>7282 本次</th><th>7452 历史同线程</th><th>表观差异</th></tr></thead><tbody>
<tr><td>CPU0，16 物理核心</td><td>57.33 GB/s</td><td>62.22 GB/s</td><td>−7.9%</td></tr>
<tr><td>CPU1，16 物理核心</td><td>57.83 GB/s</td><td>62.44 GB/s</td><td>−7.4%</td></tr>
<tr><td>双路，各 16 物理核心</td><td><b>115.08 GB/s</b></td><td>123.18 GB/s</td><td>−6.6%</td></tr>
</tbody></table></div>
<div class="table-scroll"><table><thead><tr><th>核对项</th><th>第二轮</th><th>说明</th></tr></thead><tbody>
<tr><td>CPU0 读取本地页</td><td>99.80%</td><td>严格 <code>--membind=0</code></td></tr>
<tr><td>CPU1 读取本地页</td><td>99.72%</td><td>严格 <code>--membind=1</code></td></tr>
<tr><td>双路页落点</td><td>49.65% / 50.35%</td><td>接近均匀</td></tr>
<tr><td>CPU1 原 1536MB 工作集</td><td>58.60 GB/s</td><td>与 1024MB 的 57.83 接近</td></tr>
</tbody></table></div>
<p>STREAM 的 Copy 约 61GB/s，Scale 约 40GB/s，Add/Triad 约 42GB/s；双路分别约 68/65/67GB/s。它把读写按逻辑字节计入，不能与 LIKWID 纯读取或 AIDA64 Read 直接排名。</p>
<div class="callout warning"><b>仍然存在的现象</b>：来自 <code>0000:20:01.1</code> 的 corrected PCIe/AER 事件在换回 7282 后仍出现；uncorrected 状态为 0，没有新的 fatal CPU/MCE，也没有重启。按用户说明，这属于预期内的可纠正事件。</div>
<p>结论：供电不齐时单路约 7–8GB/s 的严重低带宽没有重现；两路对称、合起来接近翻倍，说明本次补测中两条内存通路都能正常供料。与 7452 的约 6.6% 差异不能全归因于 CPU：工作集、虚拟机在线负载和后台换页都不同。</p>
<p>详细记录：<a href="AS4124-PVE-memory-7282-20261020/复测报告.md">AS4124 换回 7282 后的内存带宽复测</a>。若后续要得到更纯的 CPU 对照，可在虚拟机负载更低时用相同工作集再跑一次；本次足以排除严重低带宽。</p>
</section>
"""

TUNING = r"""
<section class="chapter" id="nightly-20261020">
<header class="chapter-head"><span class="section-number">FOLLOW-UP / 2026-10-20</span><h2>补测：从 tok/s 回到任务完成时间</h2><p class="subtitle">Strata 0.1.45 / Huihui IQ4_XS / 2×2080Ti / Hermes 工程回归</p></header>
<div class="stage-config"><b>固定条件</b><span>Huihui-Qwen3.8-Flash-Next-abliterated UD-IQ4_XS，外置 Q8_0 PLE；Strata 0.1.45；两张 2080 Ti 250W；15 workers；MTP；Hermes 0.22.1。</span><small>Agent 层每题只跑一次，题目中途修订；微测多数单次运行。</small></div>
<p>这一轮先确认基准自身有多稳，再比较参数。B0 与 B0-R2 是同一份配置的两次独立启动；4K 简单 decode 从 87.8 升到 116–125，4K 复杂从 41.9 升到 55.6–64.3。配置没变，decode 就差了 17–20%。这决定了后面只能做粗筛。</p>
<div class="table-scroll"><table><thead><tr><th>项目</th><th>结果</th><th>说明</th></tr></thead><tbody>
<tr><td>S0 参考作者组合</td><td>4K prefill 755 vs B0 984</td><td>约 −23%，无明确整体收益</td></tr>
<tr><td>会话缓存 8GiB/4槽</td><td>128K 返回 53.5–53.7s → 1.45–2.47s；32K 16s → 1.3–2.4s</td><td>恢复旧会话收益很大；普通单任务无净收益</td></tr>
<tr><td>缓存复制成本</td><td>128K 暂存 1.3–1.4s，恢复 0.6–0.7s</td><td>只在切换时支付；6.32GiB 峰值</td></tr>
<tr><td>MTP 布局</td><td>默认后卡；移到首卡四格两升两降</td><td>batch 开关未出现生效确认，不能归因</td></tr>
<tr><td>prefill-pipe</td><td>pipe=1 略好；1536 有一格异常；6144 基本持平</td><td>R 是机器相关的 b/a，必须校准</td></tr>
<tr><td>spec-min-p</td><td>0.30/0.50/0.70 复杂 decode 约 44–49 与 59–61</td><td>窗口长度与接受率互相抵消，曲线很平</td></tr>
<tr><td>250W vs 180W</td><td>整请求慢 8.25%，GPU 能量低 13.1%</td><td>prefill 慢 9.2%，decode 慢 4.7%；220W 待测</td></tr>
</tbody></table></div>
<p>12 道 Hermes 工程题两组均 12/12，总耗时 714.1s 与 715.3s，逐题几何平均 1.0164。单题有 ±30% 的摆动，T3 的 A 组工具调用 7 次对 3 次，T6 是 9 次对 7 次；路径差异比引擎几个百分点的变化大得多。</p>
<div class="callout info"><b>这轮得到的主结论</b>：tok/s 仍是中间指标；它只有在模型生成时间占任务时间较大、且解题路径稳定时才传导成任务变快。缓存对长会话切换非常有效；参数微调在短输出、单次运行下大多分不清。影响草稿窗口、采样或数值路径的参数，必须同时做正确性回归。</div>
<p><b>当前配置</b>：会话缓存已开，16 槽 / 16384MiB，最低可用内存 4GiB，少于 1024 token 不暂存；配置备份在 <code>/opt/strata-data/config/strata-huihui-ud-iq4_xs-q8ple-vision-v0.1.45.json.bak-convcache-20261020-120226</code>。切换冒烟 A→B→A：3.85s → 3.19s（暂存）→ 0.80s（复用 1553/1558 token）。</p>
<p><b>待补测</b>：MTP 长输入/长输出与生效日志；prefill-pipe 的 b/a 校准；spec-min-p 按深度接受率；220W；<code>STRATA_SPLIT_RING</code> 的 96/192/384/768；<code>parallel=2</code> 与第三张 2080 Ti。详见 <a href="Strata-Hermes-nightly-20261020/待追测清单.md">待追测清单</a> 与 <a href="Strata-Hermes-nightly-20261020/夜间测试报告.html">夜间测试报告</a>。</p>
</section>
"""

QUALITY = r"""
<section class="chapter" id="nightly-20261020">
<header class="chapter-head"><span class="section-number">FOLLOW-UP / 2026-10-20</span><h2>补测：Agent 回归 12/12，路径差异压过引擎小收益</h2><p class="subtitle">6 类工程任务 × A/B，共 12 次执行；原始配置与会话缓存候选</p></header>
<div class="stage-config"><b>判分方式</b><span>Hermes 必须在专用工作区真实读写文件、运行 SQL/代码并交付规定产物；控制器读取产物、运行隐藏测试、检查原始文件哈希。标准答案不挂进被测容器。</span><small>这是内部工程回归，不是完整 BFCL 或普遍 Agent 能力证明。</small></div>
<p>六类任务是 CSV 交易清洗、SQLite 日期排名、Python 区间修复、JSON 配置迁移、跨日志定位和三轮库存维护。原始配置和“原始配置 + 8GiB 会话缓存”都通过 12/12；总耗时 714.1s 与 715.3s，逐题几何平均 1.0164。</p>
<div class="table-scroll"><table><thead><tr><th>任务</th><th>A 组：原始 / 缓存</th><th>B 组：原始 / 缓存</th><th>观察</th></tr></thead><tbody>
<tr><td>CSV 汇总</td><td>59.6 / 58.6s</td><td>58.5 / 58.4s</td><td>稳定</td></tr>
<tr><td>SQLite 排名</td><td>51.6 / 55.8s</td><td>48.4 / 63.9s</td><td>B 组 +32%，路径/输出长度差异明显</td></tr>
<tr><td>Python 区间修复</td><td>79.0 / 64.9s</td><td>74.9 / 66.2s</td><td>A 组原始 7 次工具调用，缓存 3 次</td></tr>
<tr><td>JSON 迁移</td><td>50.6 / 48.2s</td><td>44.9 / 45.4s</td><td>接近</td></tr>
<tr><td>跨日志定位</td><td>43.3 / 46.7s</td><td>41.9 / 52.2s</td><td>B 组 +25%</td></tr>
<tr><td>三轮库存</td><td>79.3 / 73.8s</td><td>82.2 / 81.1s</td><td>原始 9 次工具调用，缓存 7 次</td></tr>
</tbody></table></div>
<p>单题摆动从 −18% 到 +32%，而两组的净差只有 1.6%。工具调用次数不同会直接改变任务时间：多两次工具、多一段检查代码，就足以盖过引擎几个百分点的速度变化。这也是“引擎快等于任务快”最需要修正的地方。</p>
<div class="callout warning"><b>证据边界</b>：最终 12/12 不是一次跑出来的。原始配置首轮 8/12，T3/T5/T6 的任务契约澄清后复跑；最终表由指定复测合成。T3 和 T6 的 A/B 输入相同，是同题重复，不是两套独立难题。原始失败轨迹全部保留。</div>
<p><b>质量风险</b>：<code>spec-min-p</code>、<code>STRATA_SPLIT_MTP_BATCH</code> 的 K/V 路径和 <code>prefill-pipe</code> 的专家集合都可能改变输出位或解题路径；速度收益小于任务噪声底时，不值得冒险。任何这类参数都应与正确性回归一起评估。</p>
<p><b>并发边界</b>：当前 <code>parallel=1</code>，两个请求严格排队；第二个请求的首 token 要等第一个完整结束。开 <code>parallel=2</code> 买到的是“第二个请求不用等几分钟”，代价是单请求变慢、专家缓存被槽位挤小；当前两张 2080 Ti 只剩约 461MiB 空闲显存。测试计划见 <a href="Strata-Hermes-nightly-20261020/待追测清单.md">待追测清单第 7 节</a>。</p>
<p><b>会话缓存</b>：16 槽 / 16GiB 已开启，少于 1024 token 不暂存；冒烟 A→B→A 为 3.85s → 3.19s → 0.80s，恢复时复用 1553/1558 token。这个测试证明恢复路径工作，但还没有对缓存开启后的回答质量做正式评测。</p>
<p>详细数据：<a href="Strata-Hermes-nightly-20261020/夜间测试报告.html">夜间测试报告</a>；待补测与验收门槛：<a href="Strata-Hermes-nightly-20261020/待追测清单.md">待追测清单</a>。</p>
</section>
"""

DOCUMENTS = [
    ("AS4124-平台排障-20261019.html", "补测：7282 带宽复核", PLATFORM),
    ("Strata-推理调优-20261019.html", "补测：夜间实验与追测", TUNING),
    ("Strata-服务质量-20261019.html", "补测：Agent 回归与并发", QUALITY),
]


def append_section(path: Path, nav_label: str, block: str) -> dict:
    text = path.read_text(encoding="utf-8")
    if f'id="{SECTION_ID}"' in text:
        raise RuntimeError(f"section already exists: {path}")
    nav_match = re.search(r"<nav\b[^>]*>.*?</nav>", text, re.S)
    if not nav_match:
        raise RuntimeError(f"nav not found: {path}")
    nav = nav_match.group(0)
    marker = '<a href="#configuration">'
    if marker not in nav:
        raise RuntimeError(f"configuration link not found in nav: {path}")
    new_nav = nav.replace(
        marker,
        f'<a href="#{SECTION_ID}">{nav_label}</a>' + marker,
        1,
    )
    text = text[:nav_match.start()] + new_nav + text[nav_match.end():]
    section_marker = '<section class="chapter" id="configuration">'
    if text.count(section_marker) != 1:
        raise RuntimeError(f"configuration section marker count: {path}")
    text = text.replace(section_marker, block + section_marker, 1)
    if text.count(f'id="{SECTION_ID}"') != 1:
        raise RuntimeError(f"section id count: {path}")
    if f'href="#{SECTION_ID}"' not in text:
        raise RuntimeError(f"nav link missing: {path}")
    backup = path.with_name(path.stem + "-before-nightly-20261020" + path.suffix)
    shutil.copy2(path, backup)
    path.write_text(text, encoding="utf-8")
    return {
        "path": str(path),
        "backup": str(backup),
        "chars": len(text),
        "new_section": f'id="{SECTION_ID}"',
    }


def main() -> None:
    for name, _, _ in DOCUMENTS:
        path = OUT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        text = path.read_text(encoding="utf-8")
        if f'id="{SECTION_ID}"' in text:
            raise RuntimeError(f"section already exists: {path}")
        nav_match = re.search(r"<nav\b[^>]*>.*?</nav>", text, re.S)
        if not nav_match or '<a href="#configuration">' not in nav_match.group(0):
            raise RuntimeError(f"navigation target missing: {path}")
        if text.count('<section class="chapter" id="configuration">') != 1:
            raise RuntimeError(f"configuration section marker missing: {path}")
    results = []
    for name, nav_label, block in DOCUMENTS:
        path = OUT / name
        results.append(append_section(path, nav_label, block))
    print("\n".join(f"{r['path']} -> {r['chars']} chars; backup={r['backup']}" for r in results))


if __name__ == "__main__":
    main()
