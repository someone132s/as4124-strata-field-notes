#!/usr/bin/env python3
"""Render the recorded nightly evidence without rerunning tests or editing results.

Both reports share this source. No SSH, HTTP, GPU, engine or Hermes calls occur.
Task examples are deterministic reconstructions from the archived suite source.
"""
from __future__ import annotations

import csv
import hashlib
import html
import importlib.util
import json
import math
import re
import statistics
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/Strata-Hermes-nightly-20261020"
TITLE = "从引擎参数到真实 Agent：Strata / Hermes 夜间测试报告"
TASK_NAMES = {
    "T1": "CSV 交易清洗与汇总", "T2": "SQLite 日期筛选与排名",
    "T3": "修复 Python 区间合并", "T4": "JSON 配置迁移",
    "T5": "跨日志定位错误源头", "T6": "三轮库存维护与会话续接",
}
ARM_NAMES = {
    "B0": "原始基准 · 首次启动", "B0-R2": "原始基准 · 第二次启动",
    "S0": "测试开始时的线上参数组合",
    "CACHE8192": "原始基准 + 8 GiB 会话缓存（最终候选）",
    "L1-SPLITMTP": "缓存配置 + MTP batch 开关",
    "L1-verify": "MTP batch 开关 · 生效复查",
    "L0-FORCE-SECOND": "缓存配置 + 显式指定后卡（即默认）",
    "L1-FORCE-SECOND-SPLIT": "显式后卡（默认）+ MTP batch 开关",
    "L2-MTPSTAGE0": "缓存配置 + 将 MTP 草稿层移到首卡",
    "PIPE1": "缓存配置 + prefill-pipe=1",
    "PIPE1536": "缓存配置 + prefill-pipe=1536",
    "PIPE6144": "缓存配置 + prefill-pipe=6144",
    "SPEC30": "缓存配置 + spec-min-p=0.30",
    "SPEC70": "缓存配置 + spec-min-p=0.70",
}
ARM_ORDER = list(ARM_NAMES)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def inline(value):
    text = html.escape(str(value))
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text.replace("\n", "<br>")


def link(label, path):
    return f"[{label}]({quote(str(path).replace(chr(92), '/'), safe='/:-_.')})"


class Report:
    def __init__(self):
        self.md = [f"# {TITLE}", ""]
        self.parts = []
        self.toc = []

    def section(self, ident, title):
        self.md += [f"## {title}", ""]
        self.parts.append(f'<h2 id="{ident}">{html.escape(title)}</h2>')
        self.toc.append((ident, title))

    def sub(self, title):
        self.md += [f"### {title}", ""]
        self.parts.append(f"<h3>{html.escape(title)}</h3>")

    def p(self, text, kind=""):
        self.md += [text, ""]
        self.parts.append(f'<p class="{kind}">{inline(text)}</p>')

    def table(self, headers, rows):
        rows = list(rows)
        escape_cell = lambda value: str(value).replace("|", "\\|").replace("\n", "<br>")
        self.md += ["| " + " | ".join(map(escape_cell, headers)) + " |",
                    "|" + "---|" * len(headers)]
        self.md += ["| " + " | ".join(map(escape_cell, row)) + " |" for row in rows]
        self.md.append("")
        self.parts.append('<div class="table-wrap"><table><thead><tr>'
                          + "".join(f"<th>{inline(x)}</th>" for x in headers)
                          + "</tr></thead><tbody>"
                          + "".join("<tr>" + "".join(f"<td>{inline(x)}</td>" for x in row)
                                    + "</tr>" for row in rows)
                          + "</tbody></table></div>")

    def code(self, title, text, language="text"):
        self.md += [f"<details><summary>{html.escape(title)}</summary>", "",
                    f"```{language}", text, "```", "", "</details>", ""]
        self.parts.append(f"<details><summary>{html.escape(title)}</summary>"
                          f"<pre><code>{html.escape(text)}</code></pre></details>")

    def chart(self, name, title, labels, series, unit, caption):
        width = 1160
        left, right, top, bottom = 315, 125, 66, 44
        bar_height, bar_gap, group_gap = 15, 4, 15
        group_height = len(series) * (bar_height + bar_gap) + group_gap
        height = top + len(labels) * group_height + bottom
        plot_width = width - left - right
        maximum = max(v for _, values, _ in series for v in values) or 1
        elements = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
                    f'role="img" aria-label="{html.escape(title)}">',
                    '<style>text{font-family:system-ui,"Microsoft YaHei",sans-serif;fill:#223342;font-size:14px}</style>',
                    f'<text x="18" y="25" font-weight="700">{html.escape(title)} · {html.escape(unit)}</text>']
        for si, (series_name, _, color) in enumerate(series):
            x = left + si * 225
            elements += [f'<rect x="{x}" y="40" width="12" height="12" fill="{color}"/>',
                         f'<text x="{x+18}" y="51">{html.escape(series_name)}</text>']
        for tick in range(5):
            x = left + plot_width * tick / 4
            elements += [f'<line x1="{x}" x2="{x}" y1="{top}" y2="{height-bottom}" stroke="#e0e7ee"/>',
                         f'<text x="{x}" y="{height-14}" text-anchor="middle">{maximum*tick/4:.1f}</text>']
        for index, label in enumerate(labels):
            y = top + index * group_height
            elements.append(f'<text x="{left-12}" y="{y+20}" text-anchor="end">{html.escape(label)}</text>')
            for si, (series_name, values, color) in enumerate(series):
                value = values[index]
                bar_width = plot_width * value / maximum
                by = y + si * (bar_height + bar_gap)
                elements += [f'<rect x="{left}" y="{by}" width="{bar_width:.2f}" height="{bar_height}" rx="2" fill="{color}">'
                             f'<title>{html.escape(label)} / {html.escape(series_name)}: {value:.3f} {html.escape(unit)}</title></rect>',
                             f'<text x="{left+bar_width+7:.2f}" y="{by+13}">{value:.2f}</text>']
        elements.append("</svg>")
        svg = "".join(elements)
        (OUT / "figures").mkdir(exist_ok=True)
        (OUT / "figures" / f"{name}.svg").write_text(svg, encoding="utf-8")
        self.md += [f"![{title}](figures/{name}.svg)", "", caption, ""]
        self.parts.append(f'<figure>{svg}<figcaption>{inline(caption)}</figcaption></figure>')

    def finish(self, metadata):
        css = """
        :root{color-scheme:light;--ink:#20313f;--muted:#5d6d7b;--line:#d8e2eb;--blue:#235b85;--bg:#f4f7fa}
        *{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:20px}
        body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.85 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
        .layout{display:grid;grid-template-columns:240px minmax(0,1120px);gap:30px;max-width:1440px;margin:auto;padding:32px 24px 80px}
        aside{position:sticky;top:24px;align-self:start;max-height:92vh;overflow:auto;font-size:13px}
        aside a{display:block;padding:7px 10px;border-left:2px solid #d9e4ed;text-decoration:none;line-height:1.5}
        aside a:hover{background:#e5edf4;border-color:var(--blue)}aside p{font-size:12px;color:var(--muted)}
        main{min-width:0}header{border-top:5px solid var(--blue);padding:24px 28px;background:white;border-radius:0 0 10px 10px;margin-bottom:28px}
        .eyebrow{font-size:12px;letter-spacing:.13em;color:var(--blue);font-weight:700}h1{font-size:32px;line-height:1.4;margin:10px 0 16px}
        h2{font-size:24px;line-height:1.45;margin:46px 0 16px;padding-bottom:10px;border-bottom:2px solid var(--line)}
        h3{font-size:19px;margin:28px 0 10px}p{margin:12px 0}a{color:var(--blue)}.meta,.note{font-size:13px;color:var(--muted)}
        .callout{background:#eaf2f8;border-left:4px solid var(--blue);padding:16px 20px;border-radius:4px}
        .warning{background:#fff4df;border-left:4px solid #b17915;padding:14px 18px;border-radius:4px}
        table{width:100%;border-collapse:collapse;background:white;font-size:14px;line-height:1.7}
        th,td{text-align:left;vertical-align:top;border:1px solid var(--line);padding:10px 12px}th{background:#eaf0f5;font-weight:650}
        tbody tr:nth-child(even){background:#f8fafc}.table-wrap{overflow-x:auto;margin:16px 0;box-shadow:0 1px 3px #20313f06}
        code{font-family:ui-monospace,Consolas,monospace;font-size:.88em;background:#e8eef4;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}
        details{background:white;border:1px solid var(--line);border-radius:6px;margin:12px 0}summary{cursor:pointer;padding:12px 15px;color:var(--blue);font-size:14px;font-weight:600}
        pre{margin:0;padding:18px;background:#192b3c;color:#e3edf6;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.75 Consolas,monospace}
        pre code{background:none;color:inherit;padding:0;font-size:inherit}figure{margin:20px 0;background:white;border:1px solid var(--line);padding:16px;border-radius:8px;overflow:auto}
        figure svg{width:100%;min-width:760px;height:auto;display:block}figcaption{font-size:13px;color:var(--muted);margin-top:12px}
        .toolbar{display:flex;gap:8px;margin:14px 0}button{padding:8px 12px;border:1px solid var(--line);border-radius:5px;background:white;color:var(--blue);cursor:pointer}
        @media(max-width:1080px){.layout{display:block;padding:20px 18px 60px}aside{position:static;max-height:none;margin-bottom:26px}nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}aside p{display:none}h1{font-size:28px}}
        @media(max-width:600px){body{font-size:15px}.layout{padding:12px}header{padding:20px}h1{font-size:25px}h2{font-size:21px}nav{grid-template-columns:1fr}th,td{padding:8px}figure{padding:8px}}
        @media print{aside,.toolbar{display:none}.layout{display:block;max-width:none;padding:0}body{background:white;font-size:11px}header{padding:8px}h1{font-size:22px}h2{font-size:18px;margin-top:25px}figure svg{min-width:0}details{break-inside:avoid}pre{background:#f3f6f9;color:#111}a{color:inherit}}
        """
        nav = "".join(f'<a href="#{i}">{html.escape(t)}</a>' for i,t in self.toc)
        page = (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{TITLE}</title><style>{css}</style></head><body><div class="layout">'
                f'<aside><b>按实验问题阅读</b><nav aria-label="报告目录">{nav}</nav>'
                '<p>正文解释实验，折叠区保留完整配置和提示词。所有图表同时提供表格原数。</p>'
                '<div class="toolbar"><button id="expand">展开全部</button><button id="print">打印</button></div></aside>'
                f'<main><header><div class="eyebrow">LOCAL INFERENCE · FIELD REPORT · 2026-10-20</div>'
                f'<h1>{TITLE}</h1><p>固定模型与硬件，分别验证冷请求速度、跨会话恢复、工具任务正确性和功耗取舍。</p>'
                f'<p class="meta">{html.escape(metadata)}</p></header>'
                + "\n".join(self.parts)
                + '</main></div><script>document.getElementById("expand").addEventListener("click",function(){'
                'const all=[...document.querySelectorAll("details")];const open=all.some(x=>!x.open);'
                'all.forEach(x=>x.open=open);this.textContent=open?"折叠全部":"展开全部";});'
                'document.getElementById("print").addEventListener("click",()=>window.print());</script></body></html>')
        (OUT / "夜间测试报告.md").write_text("\n".join(self.md) + "\n", encoding="utf-8")
        (OUT / "夜间测试报告.html").write_text(page, encoding="utf-8")


def reconstruct_tasks(manifest):
    source = ROOT / "work/hermes-bench/nightly_suite.py"
    if digest(source) != manifest["runner_sha256"]:
        raise RuntimeError("Suite source differs from archived manifest; do not reconstruct silently")
    spec = importlib.util.spec_from_file_location("nightly_suite_archive", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    examples = OUT / "task-examples"
    examples.mkdir(exist_ok=True)
    data = {}
    for task, generator in module.GENERATORS.items():
        for variant, seed in module.VARIANTS:
            name = f"{task}-{variant}"
            directory = examples / name
            if not directory.exists():
                directory.mkdir()
                oracle = generator(directory, seed)
                (directory / "expected.json").write_text(pretty(oracle) + "\n", encoding="utf-8")
            data[name] = {"path": directory, "expected": load(directory / "expected.json")}
    (examples / "T3-hidden-tests.py").write_text(module.INTERVALS_TESTS, encoding="utf-8")
    (examples / "README.md").write_text(
        "# 离线重建的任务样例\n\n这些文件由归档的 nightly_suite.py 和原始数据种子重新生成，"
        "用于阅读和复现任务，不是从远端下载的原始工作区快照，也不是新跑出的模型答案。"
        "expected.json 是控制器答案；它不曾挂载到被测 Agent 的工作区。"
        "T3-hidden-tests.py 是归档判分脚本。报告生成器没有执行 Hermes 或发出 API 请求。\n",
        encoding="utf-8")
    snapshot = {"source_sha256": digest(source), "note": "offline deterministic reconstruction, not remote raw snapshots",
                "files": {str(p.relative_to(examples)).replace(chr(92), "/"): digest(p)
                          for p in sorted(examples.rglob("*")) if p.is_file() and p.name != "manifest.json"}}
    (examples / "manifest.json").write_text(pretty(snapshot) + "\n", encoding="utf-8")
    return data, module


def selected_cases():
    files = {name: {r["case"]: r for r in load(OUT / name)["cases"]} for name in (
        "B0-suite-1-results.json", "B0-suite-3-v3-results.json", "I-suite-1-results.json",
        "I-suite-2-results.json", "I-suite-2-v3t5-results.json")}
    baseline = dict(files["B0-suite-1-results.json"])
    baseline.update(files["B0-suite-3-v3-results.json"])
    candidate = dict(files["I-suite-1-results.json"])
    for key in ("T1-a", "T1-b", "T3-a", "T3-b", "T6-a", "T6-b"):
        candidate[key] = files["I-suite-2-results.json"][key]
    candidate.update(files["I-suite-2-v3t5-results.json"])
    return baseline, candidate


def command_from_config(config):
    args = list(config["args"])
    if config.get("vision") and "--vision" not in args:
        args.append("--vision")
    if "--layer-split" not in args:
        args.extend(["--layer-split", config.get("layer_split", "auto")])
    # Display only: never execute or interpolate this shell-shaped text.
    result = [f"{config['exe']} --serve"]
    index = 0
    while index < len(args):
        token = args[index]
        if index + 1 < len(args) and not args[index + 1].startswith("--"):
            token += " " + args[index + 1]
            index += 1
        result.append("  " + token)
        index += 1
    return " \\\n".join(result)


def med(data, field):
    return statistics.median(r[field] for r in data)


def main():
    acceptance_path = OUT / "acceptance.json"
    verification_path = OUT / "final-verification.json"
    untouched = {p: digest(p) for p in (acceptance_path, verification_path)}
    a, verification = load(acceptance_path), load(verification_path)
    manifest, baseline_config = load(OUT / "suite-manifest.json"), load(OUT / "final-config.json")
    task_examples, suite = reconstruct_tasks(manifest)
    arms = {name: load(OUT / "micro" / name / "results.json") for name in ARM_ORDER}
    baseline_cases, candidate_cases = selected_cases()
    report = Report()
    report.p("实验于 **2026 年 10 月 20 日凌晨**完成。本版依据原始脚本、完整配置与结果文件补写实验背景、参数定义和任务细节；本文改写没有重新运行测试。", "note")
    report.p("**硬件时间边界：本报告记录换回 AMD EPYC 7282 之前、双路 AMD EPYC 7452 平台上的实验。** 用户随后关机换 CPU 属于下一阶段，本文不把这些成绩当作 7282 的实测结果，也不把凌晨的健康核验当作换 CPU 后的当前在线状态。", "callout")

    report.section("background", "1. 为什么做这轮测试，最后得到了什么")
    report.p("此前，我们已经解决 AS4124 的供电导致的性能异常，并比较过 worker 数、NUMA 亲和性、模型和预填充上限。新的疑问是：参考其他用户的参数后，Strata 还能否更快？单看每秒生成 token 数，是否能代表 Hermes 处理真实工具任务的效率？")
    report.p("本轮固定 Huihui 模型、外置 Q8_0 PLE、Strata 0.1.45、15 个 worker 与显卡顺序，先恢复显卡默认功耗，再分开考察四件事：冷输入的 prefill/decode、切换长会话后的恢复等待、Hermes 能否正确完成工程任务，以及降功耗的时间与能耗取舍。")
    report.table(["问题", "本轮观察", "对应决策"], [
        ["换一组引擎参数能否稳定变快？", "短微测未找到证据充分的胜出配置；不同启动的基准读数本身有明显波动。", "收尾保留原始基准参数，不宣布找到全局最优。"],
        ["会话缓存有没有用？", "128K 返回会话约 53.5–53.7 秒 → 1.45–2.47 秒；普通工具任务未显示净提速。", "把长会话恢复收益与单任务速度分开评价。"],
        ["工具任务是否做对？", "最终采用的记录中，两种配置均为 12/12；这是 6 类任务的各两次执行。", "内部回归通过，不等同完整 BFCL 或普遍 Agent 能力证明。"],
        ["180W 是否更划算？", "32K 复杂请求中位耗时增加 8.25%，GPU 能量降低 13.06%。", "按本次延迟优先门槛收尾恢复 250W；节能选择另看使用偏好。"],
    ])

    report.section("platform", "2. 测试时的平台、模型与服务")
    report.table(["项目", "本轮配置 / 证据边界"], [
        ["宿主平台", "Supermicro AS4124 双路平台；当时安装 AMD EPYC 7452。此前供电问题已排除，本轮没有更换 CPU、内存或 NUMA 配置。"],
        ["推理客机", "GPUServer-1，10.2.21.4；GPU 直通 Linux VM。此前实验留档为 32 vCPU / 128 GiB；当夜 final-verification 记录约 125.8 GiB 可见 RAM。15 workers 是引擎线程配置，不是 VM 的 vCPU 数。"],
        ["系统和驱动", "此前基准留档：PVE 宿主、推理 VM Debian 12 / Linux 6.1.0-53-amd64、NVIDIA 580.159.04、CUDA 13.0。本轮没有升级这些组件；夜间验收文件未重新保存完整版本快照，故这些是前期留档环境。"],
        ["模型全名", "huihui-ai/Huihui-Qwen3.8-Flash-Next-abliterated-GGUF，unsloth-UD-IQ4_XS，社区 abliterated（去审查）版本。API 名称：`huihui-qwen3.8-flash-next-abliterated-ud-iq4_xs`。"],
        ["模型与 PLE", "三分片 GGUF；外置 Q8_0 PLE，并用全部 native-dense 分片覆盖 dense 权重来源；本轮没有切回 SC117 IQ3。"],
        ["引擎", "Strata 0.1.45；执行方案核验的源码 commit：477ac13cbe8e582c20484871ce459d20d82df09d。"],
        ["文本推理显卡", "2 × RTX 2080 Ti 22 GiB。参数筛选时每张上限 250W；功耗对照时比较每张 250W / 180W。"],
        ["视觉显卡", "RTX 2070 SUPER 8 GiB，215W；视觉 token 上限 16384，threads 16。本轮没有图片请求，不能据此评价视觉速度。"],
        ["Agent 客户端", "Hermes-1，10.2.21.6；v0.22.1+163.g046094d；使用独立测试 home、题目工作区和 rootless Docker。"],
        ["接口与并发", "`http://10.2.21.4:8080/v1/chat/completions`；串行执行。服务配置 `parallel=1`，`pipeline-windows=2`，两者不是同一个概念。"],
    ])
    report.p("本报告中的“4K / 32K / 128K”表示近似输入 token 档位，实际数量以逐请求记录为准；“8192 MiB 会话缓存”表示容量预算，不是上下文 token 数。", "note")

    report.section("baseline", "3. 先把基准参数说清楚：B0、S0 和 I 是什么")
    report.p("**B0 = 抄参考作者参数之前的原始配置。** 本轮先把两张 2080 Ti 恢复到每张 250W，再重新测量这个配置。“B0-R2”只是同一份配置的第二次启动和复测，并不代表新参数。")
    report.p("**S0 = 夜间开始时线上正在使用的配置。** 它已经包含之前参考作者时加入的若干参数；本轮把它作为一个整体组合与原始配置比较。**I = 最终进入 Agent 验收的候选**，实际是 B0 加上 8192 MiB / 4 槽会话缓存。下文直接写中文配置名，代号仅用于对应文件名。")
    report.table(["参数 / 项目", "原始基准 B0", "开始时线上组合 S0", "最终候选 I"], [
        ["模型 / 引擎 / worker", "Huihui UD-IQ4_XS / 0.1.45 / 15", "相同", "相同"],
        ["`--prefill` / `--prefill-pipe`", "`auto:8192` / 实际 0", "相同", "相同"],
        ["`--spec` / `--spec-min-p`", "`4` / `0.50`", "`4` / **`0.70`**", "`4` / `0.50`"],
        ["`--mtp-hnorm` / `--pipeline-windows`", "`stream` / `2`", "相同", "相同"],
        ["`--layer-split`", "`auto`（由服务配置传入）", "`auto`", "`auto`"],
        ["`--kv` / `--kv-resident`", "`int8` / `32768`", "相同", "相同"],
        ["`--max-context` / `--resident-budget-gib`", "`262144` / `55`", "相同", "相同"],
        ["`--ple-io` / `--expert-cache`", "`ram` / `auto`", "相同", "相同"],
        ["`--vram-reserve-mib` / `--vram-reserve-later-mib`", "`700` / `700`", "**`500` / `600`**", "`700` / `700`"],
        ["`--conversation-cache-mib`", "未显式指定；运行时确认为 **0**", "显式 `0`", "**`8192`**"],
        ["`--conversation-cache-slots`", "运行时默认 `4`", "显式 `4`", "显式 `4`"],
        ["`STRATA_SELECT_SIMT`", "未设置", "**`2`**", "未设置"],
        ["`STRATA_REFILL_PARTS` / `STRATA_PREFILL_HELP`", "未设置 / 未设置", "**`1` / `1`**", "未设置 / 未设置"],
        ["公共环境变量", "`STRATA_BF16_TC=1`、`STRATA_STAGE_TRIM=1`、`STRATA_SM75_PERF=1`、`STRATA_PA_V2T=1`", "相同", "相同"],
        ["GPU 功耗上限（筛选 / Agent）", "每张 2080 Ti 250W", "相同", "相同"],
    ])
    report.p("表中“未设置”只说明配置文件没有显式覆盖该环境变量，不自动等于数值 0。`--spec=4` 是保存的命令行值；最终 `/metrics` 同时报告 `spec=6`、`mtp_max=4`、`lookup=3`，这些字段的含义不同，不能把运行时字段拼回另一个启动命令。", "note")
    report.code("原始基准：完整引擎命令（根据保存配置展开；只供复现阅读）", command_from_config(baseline_config), "bash")
    report.code("原始基准：完整服务 JSON（含采样、GPU 顺序、视觉参数与模型 SHA256）", pretty(baseline_config), "json")
    report.code("测试结束时的真实进程命令与环境", verification["process"]["stdout"].strip()
                + "\n\n" + pretty(verification["selected_engine_env"]), "text")
    report.p("完整 JSON 还保留服务默认采样：temperature 1.0、top_p 0.95、top_k 20、min_p 0；服务默认 reasoning_effort 为 high、预算 32768。下节会分别列出微测与 Hermes 的设置，不能把这些服务默认值当成所有请求的实际采样值。")

    report.section("protocol", "4. 四类测试分别怎么测，哪些成绩可以比较")
    report.table(["协议", "测试内容", "预热与重复（实际执行）", "计时 / 判分来源"], [
        ["引擎冷请求微测", "4K 简单、4K 复杂、32K 简单、32K 复杂；每个请求最多输出 512 token。", "每个参数组重建引擎；一次 4K 简单请求预热，最多输出 64 token。大多每题 1 次，部分组 2 次；组别明细见第 5 节。", "自写 run_micro_arm.py；prefill/decode 取 Strata `/metrics`，流式首输出和总耗时由客户端记录。本轮不是 EvalScope。"],
        ["会话切换恢复", "在 32K、128K 输入档位执行 A → B → A → B；同一侧返回时输入保持一致，最多输出 16 token。", "分别比较缓存 0 与 8192 MiB / 4 槽。每个长度两次返回请求；32K 开启组有归档缺口，单独标注。", "自写 cache_probe.py；客户端整请求耗时，以及引擎 reused / prompt_total / cache 统计。"],
        ["Hermes 工程任务", "6 类任务 × A/B 两次执行；真实 terminal/file 工具循环；T6 包含 3 轮用户要求。", "每题独立工作区与 Hermes home；T6 内续接同一个 session。受题目修订影响，最终表由指定复测记录合成。", "nightly_suite.py 的外层 subprocess 墙钟；控制器读取产物、运行隐藏测试、检查原始文件哈希。"],
        ["GPU 功耗对照", "同一 32K 复杂请求，最多输出 512 token；只改变两张文本 GPU 的功耗上限。", "250、180、180、250、250、180W；每档 3 次。切换后等待 5 秒，并先发一次 64 token 预热请求；不重启引擎。", "自写 power_compare.py；客户端墙钟和引擎速度；流式读取期间从 `/metrics` 采集 GPU 功率，分段积分得到能量。"],
    ])
    report.sub("冷请求的简单文本与复杂文本究竟是什么")
    report.p("两种请求都读取同一来源的口腔临床记录材料，正文按输入档位裁切。简单任务要求“从 1 开始逐行数到 1000”；复杂任务要求分析“口腔临床记录中信息完整性与可追溯性的关系、记录偏差环节和改进建议”。后者用于观察非重复自然语言输出，不能把两者的 decode 平均当成统一工作负载。")
    report.p("微测从 `outputs/numa-affinity-sweep-20261019/requests.jsonl` 复用固定正文；请求 temperature=0、top_p=0.95、top_k=20、seed=20261019、reasoning_effort=none。脚本把输出上限由原请求的 1000 改为 512，并在开头加上参数组/轮次标记以避免前缀复用。不同组标记不同，因此输入正文相同但并非逐字节完全相同；表中保留实际输入 token 与 `reused`。")
    bodies = [json.loads(line) for line in (ROOT / "outputs/numa-affinity-sweep-20261019/requests.jsonl").read_text(encoding="utf-8").splitlines()]
    request_settings = {k: v for k, v in bodies[0].items() if k != "messages"}
    request_settings.update(max_tokens=512)
    report.code("冷请求：请求字段及两个任务的原始末尾指令", pretty(request_settings) + "\n\n简单任务：\n"
                + bodies[0]["messages"][0]["content"].split("</材料>")[-1].strip()
                + "\n\n复杂任务：\n" + bodies[1]["messages"][0]["content"].split("</材料>")[-1].strip(), "text")
    report.sub("三个时间指标不能混用")
    report.table(["指标", "本报告的定义"], [
        ["prefill tok/s", "微测使用引擎 prompt_tokens ÷ (prompt_ms / 1000)。冷请求已检查 reused=0；不套用于命中缓存的恢复请求。"],
        ["decode tok/s", "直接采用引擎逐请求的 decode_tok_s。它反映生成阶段，不能替代用户等待整项任务的时间。"],
        ["首输出 / TTFT", "客户端收到第一个包含 content 或 reasoning_content 的流事件；脚本另存首个可见 content。两者均不等于完整工具调用已生成。"],
        ["Agent 总耗时", "一题中 Hermes CLI 子进程耗时之和，包含客户端启动、工具与模型交互；不包含输入生成和最后判分耗时。T6 为三轮之和。"],
        ["128K 返回会话耗时", "非流式请求的完整返回时间，含最多 16 token 输出；它不是严格意义上的 TTFT。"],
    ])
    report.p("本轮没有为每道 Agent 题归档一份完整的逐模型请求 prefill/decode 汇总；因此 Agent 结果只报告可核验的任务耗时、工具次数和正确性。我们不从 Agent 总时间倒推某个未测到的 prefill 或 decode。", "note")

    report.section("arms", "5. 每组到底改了什么：完整实验矩阵")
    report.p("下面先列参数，再看成绩。**除了原始基准与 S0，后续 MTP、prefill-pipe、阈值候选都继承了开启会话缓存的配置。** 因而它们与原始基准的差异包含缓存；例如 PIPE1536 对“缓存候选”的比较才接近单变量对照，不能把它对 B0 的全部差异归给 prefill-pipe。", "callout")
    matrix = []
    for name in ARM_ORDER:
        arm = arms[name]
        parent = "原始基准 B0" if name in ("B0", "B0-R2", "CACHE8192") else ("开始时线上配置" if name == "S0" else "B0 + 8 GiB / 4 槽缓存")
        delta = (arm.get("set_arg") or []) + (arm.get("set_env") or [])
        if name == "S0":
            delta = ["spec-min-p=0.70；显存预留500/600；SELECT_SIMT=2；REFILL_PARTS=1；PREFILL_HELP=1"]
        if not delta:
            delta = ["无参数变化；独立启动" + ("后每题复测2次" if name == "B0-R2" else "后每题测1次")]
        repeats = len({r["repeat"] for r in arm["rows"]})
        note = "仅初筛，无完整3对交错复测"
        if name in ("L1-SPLITMTP", "L1-verify", "L1-FORCE-SECOND-SPLIT"):
            note = "开关存在，但未获得 batched-path 生效确认"
        if name == "L2-MTPSTAGE0": note = "真正移到首卡；四格两升两降，未形成稳定方向"
        matrix.append([f"{ARM_NAMES[name]}\n`{name}`", parent, "；".join(delta), f"每题 {repeats} 次，共 {len(arm['rows'])} 条", note])
    report.table(["中文名称 / 归档代号", "继承哪份配置", "本组显式改变", "测量数量", "证据级别"], matrix)
    report.p("prefill-pipe 的数值按引擎参数原样记录，不把 1536/6144 解释成实际处理的 chunk token 数。MTP batch 未确认生效的组既不能证明该优化有用，也不能证明该优化无效。")
    for name in ARM_ORDER:
        config = load(OUT / "micro" / name / "candidate-config.json")
        report.code(f"{ARM_NAMES[name]}（{name}）：完整命令与全部显式环境变量",
                    command_from_config(config) + "\n\n# 配置中显式设置的环境变量\n" + pretty(config.get("env", {})), "text")

    report.section("micro", "6. 冷请求结果：同时看 prefill、decode 和启动波动")
    report.p("原版报告把 4K 的简单/复杂 prefill 合并为一个中位数，又把不同长度的 decode 合并显示，容易遮住任务差异。此版按 **4K 简单、4K 复杂、32K 简单、32K 复杂**分别展示；每项同时列 prefill 与 decode。一个单元格中的数值仅在同一参数组、同一题型内取重复中位数。")
    labels = ["4K-simple", "4K-complex", "32K-simple", "32K-complex"]
    micro_rows = []
    for name in ARM_ORDER:
        cells = [ARM_NAMES[name] + f"\n`{name}`"]
        for label in labels:
            records = [r for r in arms[name]["rows"] if r["label"] == label]
            cells.append(f"{med(records, 'prefill_tok_s'):.1f} / {med(records, 'decode_tok_s'):.1f}")
        micro_rows.append(cells)
    report.table(["配置", "4K 简单\nprefill / decode", "4K 复杂\nprefill / decode",
                  "32K 简单\nprefill / decode", "32K 复杂\nprefill / decode"], micro_rows)
    report.p("表中两项速度的单位均为 tok/s，越高越快。完整逐请求表在下方，包含客户端耗时、首输出和实际复用量；没有把每个指标合成一个总分。", "note")
    first, second = arms["B0"]["rows"], arms["B0-R2"]["rows"]
    report.chart("baseline-startup-variance", "同一份原始配置，两次启动的 decode", ["4K 简单", "4K 复杂", "32K 简单", "32K 复杂"],
                 [("首次启动", [med([r for r in first if r['label']==label], 'decode_tok_s') for label in labels], "#8094a8"),
                  ("第二次启动（组内中位数）", [med([r for r in second if r['label']==label], 'decode_tok_s') for label in labels], "#286a99")],
                 "tok/s", "两次配置相同；第二次启动每题2次，第一次每题1次。这张图说明基准存在启动/运行状态波动，不能把后续小差异直接归因于参数。")
    report.p("例如同一原始配置的 4K 简单 decode，首次为 87.8 tok/s，第二次两次为 116.0 和 125.3 tok/s。多数候选只测一遍，又未完整执行计划中的稳定性门槛和三对交错复测，因此微测可以用来决定暂不晋级，但不足以对参数做严格因果排序。", "warning")
    report.p("有两处旧版描述需要按源码和日志修正。CUDA 构建默认把草稿层放在后卡；L0 只是把这个默认值显式写出，L2 才是把草稿层移到前卡。L0、L2 与同为默认布局的缓存基准在四格中互有胜负，彼此又能差出 17%，说明这一组的名次主要受启动状态影响，不能据此判定某种布局更快。prefill-pipe 1536 的 4K 简单请求只有 631 tok/s 的 prefill 和 58.9 的 decode，但同组 4K 复杂的 prefill 是 899，32K 两格也正常，且该请求的草稿接受率仍有 97.5%；这更像一次运行异常。汇总中位数被它拉低，不应据此判定该功能无效。", "warning")
    details_rows = []
    for name in ARM_ORDER:
        for row in arms[name]["rows"]:
            details_rows.append([name, row["label"], row["repeat"]+1, row["prompt_tokens"], row["output_tokens"],
                                 row["prefix_reused"], f"{row['prefill_tok_s']:.1f}", f"{row['decode_tok_s']:.1f}",
                                 f"{row['stream_first_s']:.2f}", f"{row['wall_s']:.2f}",
                                 "—" if row.get("draft_accept_rate") is None else f"{row['draft_accept_rate']*100:.1f}%"])
    report.md += ["<details><summary>全部冷请求原数：输入、复用、prefill、decode 与客户端耗时</summary>", ""]
    report.parts.append("<details><summary>全部冷请求原数：输入、复用、prefill、decode 与客户端耗时</summary>")
    report.table(["归档组", "任务", "轮次", "输入token", "输出token", "复用token", "prefill tok/s", "decode tok/s", "首输出秒", "整请求秒", "草稿接受比例"], details_rows)
    report.md += ["</details>", ""]
    report.parts.append("</details>")

    report.section("tasks", "7. Hermes 实际做了哪些任务，怎样判定做对了")
    report.p("这不是让模型口头回答一道选择题。Hermes 需要在 `/workspace` 内读文件、运行代码或 SQL、写出规定产物，控制器随后独立判分。题目输入和提示词按固定规则生成，标准答案与隐藏测试不挂载到被测 Agent 的工作区。")
    report.p("**T1–T6 是六类任务；a、b 是两次执行的标识。** 数据生成种子分别为 20261020、20261021，它们不是模型采样 seed。T1、T2、T4、T5 的输入随数据种子变化；T3 的代码与测试、T6 的初始库存和三轮变更完全相同，所以这两类的 a/b 是同题重复，不应描述成两套独立难题。")
    report.table(["代号", "中文任务", "模型需要交付", "可信判分方法"], [
        ["T1-a / T1-b", TASK_NAMES["T1"], "读取 transactions.csv，按客户写出整数分汇总 result.json。", "解析后的 JSON 与控制器 oracle 精确相等；原 CSV 哈希不变。"],
        ["T2-a / T2-b", TASK_NAMES["T2"], "只读查询 sales.db，输出 2026年9月已付款客户排名。", "与生成器用可信 SQL 计算的完整列表精确比较；原数据库哈希不变。"],
        ["T3-a / T3-b", TASK_NAMES["T3"], "只修改 intervals.py，使区间重合/共享端点合并，并处理非法输入。", "独立只读验证容器运行 20 个结果用例 + 3 个异常用例；原有其他文件哈希不变。"],
        ["T4-a / T4-b", TASK_NAMES["T4"], "从 config-old.json 迁移出规定结构的 result.json。", "比较所有字段、类型、数组顺序与未知字段；原 JSON 哈希不变。"],
        ["T5-a / T5-b", TASK_NAMES["T5"], "从四份日志提取首个失败组件、传播链与用户响应码。", "按请求 ID、错误码、组件与边序列精确比较 result.json；输入日志不变。"],
        ["T6-a / T6-b", TASK_NAMES["T6"], "三轮中创建 SQLite 库存、应用增减、执行纠正并输出最终库存。", "检查最终 inventory.json 与数据库查询结果；另外记录三轮 session ID 是否一致。"],
    ])
    task_descriptions = {
        "T1": [
            "输入有6名客户、18笔基础订单，部分订单带更高版本，并可能包含取消单和退款；行顺序打乱。Agent 必须对每个 order_id 先保留最大 version，而不是逐行直接累加。paid 销售加金额和订单数，cancelled 不计，posted 退款减金额并增加退款数。金额全程使用整数分，客户按姓名排序。",
            "产物只包含 currency=USD 和 customers 数组；每位客户必须有 customer、total_cents、paid_orders、refunds。两个数据种子里，A组没有退款行，B组含退款，因此“退款处理通过”的证据主要来自B组。"],
        "T2": [
            "输入数据库包含 customers、orders、payments 三张表：8名客户、40笔随机日期订单，外加2笔边界订单。Agent 必须关联三表，仅保留 paid，时间窗口是 [2026-09-01T00:00:00Z, 2026-10-01T00:00:00Z)。",
            "9月30日23:59:59的4444分订单应计入；10月1日00:00:00的999999分订单必须排除。按金额降序、客户ID升序排列，rank取1、2、3……；不是并列名次。产物保留精确 window 字符串和完整 rows。"],
        "T3": [
            "初始 merge_intervals 只用 start < last_end 判断合并，漏掉共享端点的情况，也没有完成输入验证。要求返回按起点排序的新区间列表，支持乱序、重复、嵌套、负数与零长度区间。",
            "本题的“接触”仅指共享端点：(1,3)+(3,5)应合并成(1,5)；(0,0)+(1,1)保持分开。start>end要报ValueError；不是恰好两个整数边界的输入要报TypeError。隐藏测试包含20个正常用例和3个非法输入，不能把它称作覆盖整个Python输入域的完整验证。要求不修改传入对象，但当前隐藏脚本没有独立的非变异断言。"],
        "T4": [
            "旧JSON包含顶层service名称、listen地址、enabled、重复features、以字符串表示的limits，以及owner、release、legacy_note等未知字段。Agent 需要把listen拆成host和整数port，把service名称与enabled放入service对象。",
            "features区分大小写、去重后排序；两项limits转整数；未知顶层字段原样放入extra。最终顶层只能有service、features、limits、extra，不能覆盖或修改config-old.json。旧提示词写过service.listen，但生成文件中的listen实际在顶层；报告保留原文，同时说明实际输入结构。"],
        "T5": [
            "四份合成日志分别为edge、payments、orders和gateway。edge记录正常接入，payments最先产生ERR_PAYMENT_503，再传给orders，orders再传给gateway；gateway最终给用户422。",
            "Agent 不能把最后报错的gateway当根因，也不能把正常edge入口或gateway到用户的响应加进错误传播链。标准链只有 payments→orders、orders→gateway；产物还必须包含目标request_id、first_failure_component=payments、first_failure_code=ERR_PAYMENT_503、user_response=422。"],
        "T6": [
            "第1轮：从seed.csv把A-100/Anvil=12、B-200/Bolt=7、C-300/Clamp=20载入inventory.db，表结构包含sku、name、qty、updated_at，并写turn1.json。第2轮：读取changes2.json，依次对三项应用-4、+8、-6，写turn2.json。",
            "第3轮：读取correction3.json，把C-300设为11，不能重建数据库或重新读取seed.csv，写inventory.json。最终A-100=8、B-200=15、C-300=11。控制器核验最终JSON和SQLite查询同时正确，并记录三轮同一session。当前grade函数没有逐项判分turn1/turn2，也没有把session_preserved并入passed，所以报告单独核对最终保存的续接记录，不夸大自动判分范围。"],
    }
    for task, paragraphs in task_descriptions.items():
        report.sub(f"{task} · {TASK_NAMES[task]}")
        for paragraph in paragraphs: report.p(paragraph)
        entry = task_examples[f"{task}-a"]
        directory = entry["path"]
        prompt_paths = sorted(directory.glob("prompt*.txt"))
        report.code(f"{TASK_NAMES[task]}：A组原始提示词（T6含三轮）", "\n\n".join(
            f"--- {p.name} ---\n{p.read_text(encoding='utf-8')}" for p in prompt_paths), "text")
        report.code(f"{TASK_NAMES[task]}：A组控制器标准答案", pretty(entry["expected"]), "json")
        if task == "T3":
            report.code("代码修复题：初始错误实现", suite.INTERVALS_INITIAL, "python")
            report.code("代码修复题：全部23个隐藏检查的原始脚本", suite.INTERVALS_TESTS, "python")
        report.p("离线样例：" + link("A组输入与提示词", f"task-examples/{task}-a/") + "；"
                 + link("B组输入与提示词", f"task-examples/{task}-b/") + "。这些是按归档源码和种子重新生成的阅读材料，不是新执行的模型结果。", "note")

    report.section("agent-settings", "8. Hermes 的运行参数与隔离方式")
    report.table(["设置", "实际脚本中的值 / 作用"], [
        ["模型调用", "专用 strata-nightly provider，指向10.2.21.4:8080/v1；openai_chat；不使用外部fallback。"],
        ["工具", "`--toolsets terminal,file`；工作区位于专用Docker容器的/workspace；题目容器网络关闭。"],
        ["Hermes reasoning", "配置文件设medium；不是微测的none。服务JSON默认high与客户端medium分别属于两层配置。"],
        ["轮数与时间", "Hermes max_turns=12、run_budget_seconds=285；普通题外层子进程timeout=300秒。T6逐轮使用剩余时间，但至少给30秒；12轮限制是每次CLI调用的设置，不是严格的三轮总和限制。"],
        ["资源", "容器2 CPU、4096 MiB内存、2048 MiB磁盘；terminal timeout=90秒、lifetime=300秒。"],
        ["状态", "每题独立home和workspace；关闭Hermes记忆、用户画像、上下文压缩、插件、MCP和fallback；T6使用--resume续接。"],
        ["采样证据", "Agent执行器没有逐请求显式设置temperature、seed或max_tokens；配置保留模型服务默认值，但不能声称每次请求都已抓取并证实相同采样字段。a/b只固定数据生成种子。"],
        ["计分", "与控制器oracle比较最终文件；输入哈希检查允许改intervals.py，其余原始文件不可变；代码题在独立只读容器验证。"],
    ])
    report.code("Hermes 正式题配置模板（来自实际执行器）", suite.hermes_config(Path("/home/hermes/strata-bench/<run>/cases/<case>/workspace")), "yaml")
    report.code("Hermes CLI 调用形状（真实脚本；T6第2/3轮追加--resume）", """/home/hermes/.local/bin/hermes chat --oneshot \\
  --query-file <case>/prompt.txt \\
  --in <case>/workspace \\
  --toolsets terminal,file \\
  --ignore-rules --yolo --format stream-json --max-turns 12

# T6后续用户轮：同一home与workspace，追加
# --resume <上一轮的session_id>
# HERMES_HOME为本题专用目录；Docker工具网络关闭；标准答案不挂进容器。""", "bash")

    report.section("agent-results", "9. Agent 结果：把 T1-a 换成能读懂的任务名称")
    report.p("进入最终验收的是“原始参数、缓存关闭”和“相同参数、8 GiB / 4 槽缓存”。本节比较整项任务的正确性与耗时，不使用冷请求微测代替Agent成绩。")
    agent_rows = []
    b0_sources, i_sources = {}, {}
    for case in a["agent"]["cases"]:
        key = case["case"]
        task, variant = key.split("-")
        left, right = baseline_cases[key], candidate_cases[key]
        if not math.isclose(case["baseline_s"], left["duration_s"], abs_tol=0.011):
            raise RuntimeError("Acceptance baseline source mismatch: " + key)
        if not math.isclose(case["candidate_s"], right["duration_s"], abs_tol=0.011):
            raise RuntimeError("Acceptance candidate source mismatch: " + key)
        b0_sources[key] = "B0-suite-1" if task in ("T2", "T4") else "B0-suite-3-v3"
        i_sources[key] = "I-suite-1" if task in ("T2", "T4") else ("I-suite-2-v3t5" if task == "T5" else "I-suite-2")
        agent_rows.append([f"{TASK_NAMES[task]} · {variant.upper()}组\n`{key}`", f"{left['duration_s']:.2f}",
                           f"{right['duration_s']:.2f}", f"{right['duration_s']/left['duration_s']:.3f}",
                           f"{left.get('tool_calls',0)} / {right.get('tool_calls',0)}", "双方通过"])
    report.table(["实际任务", "缓存关闭 秒", "8GiB缓存 秒", "候选/基准", "工具调用次数\n基准/候选", "判分"], agent_rows)
    report.p(f"两组均通过 {a['agent']['total']}/12。原始配置总耗时 {a['agent']['baseline_total_seconds']:.2f} 秒，缓存候选 {a['agent']['candidate_total_seconds']:.2f} 秒；逐题耗时比的等权几何平均为 {a['agent']['candidate_to_baseline_geomean']:.5f}，即候选在这个汇总指标上慢约 1.64%。不同指标的权重不同，因此累计总耗时与几何平均不是同一个百分比。")
    report.chart("agent-paired-times", "真实工程任务的完成时间", [TASK_NAMES[r['case'].split('-')[0]].replace("与会话续接", "") + " " + r['case'].split('-')[1].upper() for r in a['agent']['cases']],
                 [("原始参数，缓存关闭", [r['baseline_s'] for r in a['agent']['cases']], "#286a99"),
                  ("相同参数，8GiB会话缓存", [r['candidate_s'] for r in a['agent']['cases']], "#d08a39")],
                 "秒，越短越快", "每对横条是一道具体任务；T6含三轮用户要求。表中正确性和时间来自最终指定记录，非全部历史轮次的均值。")
    report.p("预设自动晋级要求包括：正确性不退化且至少11/12、逐题耗时几何平均至少降低8%、至少8/12题不更慢、累计耗时不能变差，以及其他回归条件。候选在速度条件上没有通过，因此测试结束保留缓存关闭的原始配置。8%是本次决策门槛，不是统计显著性检验；现有数据不足以证明缓存稳定地使普通Agent任务变慢。")
    report.sub("为什么出现过失败，最终表为何不是第一遍成绩")
    report.p("初始原始配置通过8/12：T3-a、T5-a、T6-a、T6-b未通过。随后发现区间“接触”定义不清、错误传播链范围不清，以及T6判分对象与最终JSON结构不一致。执行过程修改了题目契约/判分并复跑；候选的T5-a也曾在中间轮次失败，之后使用澄清后的同一契约重跑。")
    report.p("最终表沿用归档 acceptance.json 的选样规则：T2/T4沿用首轮，T1/T3/T5/T6使用指定复测。它不是两份完全不经修订的一次性全套对照，也不是每道题多次重复后的中位数。新版保留每次失败和逐题来源，避免把复测后12/12误写成从未失败。", "warning")
    round_rows = []
    for path in sorted(OUT.glob("*suite*results.json")):
        result = load(path)
        failures = [r["case"] for r in result["cases"] if not r.get("passed")]
        round_rows.append([path.name, f"{sum(bool(r.get('passed')) for r in result['cases'])}/{len(result['cases'])}", "、".join(failures) or "无", link("原始结果", path.name)])
    report.table(["实际轮次文件", "通过/执行", "失败题", "追溯"], round_rows)
    report.code("最终每题采用哪一份记录", pretty({k: {"baseline": b0_sources[k], "candidate": i_sources[k]} for k in b0_sources}), "json")
    t6_sessions = [{"case": key, "baseline_session_preserved": baseline_cases[key].get("session_preserved"),
                    "candidate_session_preserved": candidate_cases[key].get("session_preserved"),
                    "baseline_cli_calls": len(baseline_cases[key]["calls"]), "candidate_cli_calls": len(candidate_cases[key]["calls"])} for key in ("T6-a", "T6-b")]
    report.code("三轮库存任务：最终记录中的真实续接检查", pretty(t6_sessions), "json")

    report.section("cache", "10. 会话缓存：为什么普通任务不变快，恢复长会话却很快")
    report.p("关闭 conversation cache 不代表所有前缀复用都被关闭：活动会话仍可能复用连续前缀。此次专项测试针对的是先处理A、再处理B、然后回到A、再回到B时，先前会话状态能否恢复。它与一个任务连续跑完的工具循环不是同一种负载。")
    report.p("测试按长度准备A/B两份固定正文，顺序发出A1、B1、A2、B2；A2与A1同侧提示词一致，B2与B1一致。每次最多输出16 token。开启组设置`--conversation-cache-mib 8192 --conversation-cache-slots 4`，关闭组预算为0；图表统计的是A2/B2整请求耗时，而不是首 token 时间。")
    cache_rows = []
    for row in a["cache"]["by_length"]:
        evidence = "结构化原始结果" if not row.get("source") else "执行时控制台记录；未保留对应结构化轮次"
        cache_rows.append(["关闭" if row["state"] == "off" else "8192 MiB / 4槽", row["length"],
                           f"{row['A_return_s']:.3f}", f"{row['B_return_s']:.3f}", row["A_return_reused"], evidence])
    report.table(["会话缓存", "输入档位", "回到A 秒", "回到B 秒", "A复用token", "数据来源"], cache_rows)
    on128 = next(r for r in a["cache"]["by_length"] if r['state']=='on' and r['length']=='128K')
    off128 = next(r for r in a["cache"]["by_length"] if r['state']=='off' and r['length']=='128K')
    report.chart("cache-128k-return", "128K 会话切换后再次返回", ["回到会话A", "回到会话B"],
                 [("缓存关闭", [off128['A_return_s'], off128['B_return_s']], "#8094a8"),
                  ("8GiB / 4槽会话缓存", [on128['A_return_s'], on128['B_return_s']], "#286a99")],
                 "秒，越短越快", "仅画有完整结构化记录的128K档位；每根条是一次返回请求，不是多轮统计置信区间。")
    report.p(f"128K开启组复用131081个token，实际prompt_total为131088，约占99.995%；关闭组复用为0。缓存记录中占用6787646776字节，即 **{a['cache']['peak_cache_bytes']/1024**3:.2f} GiB**（6473.20 MiB），预算8192 MiB。归档的最后一次缓存状态含parks=16、restores=4、evictions=9，这些是该引擎进程的累计计数，不应全部当作这四次请求单独产生的计数。")
    report.p("32K开启时约1.3–2.4秒的结果来自执行时控制台观察，已写入acceptance，但cache/CACHE8192/results.json只保存了128K轮次。因此32K开启数据可以保留为辅助观察，不能冒充与128K相同完整度的原始证据。", "note")
    report.p("这一结果支持“反复切换长历史任务时值得使用会话缓存”。它没有证明新任务的冷prefill会更快，也没有证明decode会更快。最终自动验收仍按普通工程任务的门槛保留缓存关闭；实际部署可根据长会话恢复频率单独选择。")

    report.section("power", "11. 功耗对照：250W 与 180W 换来了什么")
    power = load(OUT / "power/results.json")
    report.p("在最终原始配置上，脚本实时修改两张2080 Ti的功耗上限，保持2070 SUPER为215W。六次正式请求顺序是250、180、180、250、250、180W；每次正式测量前都先预热。输入是相同32K复杂材料任务，实际32777 token，输出512 token，reused=0。")
    report.p("脚本在接收流事件时按至少0.2秒间隔尝试读取`/metrics`的gpu_power和gpu_temp，再以相邻样点间隔做功率积分；prefill期间没有独立后台采样线程，所以采样并不覆盖每个时段且不保证固定频率。这里的能量是引擎报告的两张文本GPU功率积分估计，不是三卡总能耗，也不是整机插座电量。", "note")
    power_rows = []
    grouped = {}
    for watts in (250, 180):
        rows = [r for r in power["rows"] if r["power_limit_w"] == watts]
        grouped[watts] = rows
        power_rows.append([f"每张 {watts}W", len(rows), f"{med(rows,'wall_s'):.3f}",
                           f"{statistics.median(r['backend']['prompt_tokens']/(r['backend']['prompt_ms']/1000) for r in rows):.1f}",
                           f"{statistics.median(r['backend']['decode_tok_s'] for r in rows):.1f}",
                           f"{med(rows,'gpu_energy_j')/1000:.3f}", max(r['gpu_temp_max_c'] for r in rows)])
    report.table(["GPU上限", "次数", "整请求中位数 秒", "prefill中位数 tok/s", "decode中位数 tok/s", "GPU能量估计中位数 kJ", "组内最高温 ℃"], power_rows)
    report.chart("power-latency", "功耗上限与请求等待", ["同一32K复杂任务"],
                 [("每张250W", [med(grouped[250], 'wall_s')], "#286a99"),
                  ("每张180W", [med(grouped[180], 'wall_s')], "#d08a39")], "秒", "只比较整请求时间；能量单列，避免把秒与焦耳放到同一个数轴。")
    report.p(f"180W的整请求中位耗时增加{a['power']['slowdown_180']*100:.2f}%，GPU能量估计降低{-a['power']['energy_change_180']*100:.2f}%。本轮预设节能推荐门槛是耗时增加不超过3%、GPU能量下降至少10%，180W没有满足延迟条件，所以收尾恢复250W。它仍可能适合愿意用约8%等待时间换取节能的用户；本轮没有测220W，不能宣称250W是最佳能效点。")
    report.table(["正式次序", "每张上限W", "整请求秒", "prefill tok/s", "decode tok/s", "GPU能量估计J", "最高温℃"], [
        [i+1, r['power_limit_w'], f"{r['wall_s']:.3f}", f"{r['backend']['prompt_tokens']/(r['backend']['prompt_ms']/1000):.1f}",
         f"{r['backend']['decode_tok_s']:.1f}", f"{r['gpu_energy_j']:.1f}", r['gpu_temp_max_c']] for i,r in enumerate(power['rows'])])

    report.section("limits", "12. 证据能支持到哪里，还有哪些没有测完")
    report.p("本轮完成了多组微测、长会话缓存功能验证、两种配置的工程任务判分与250/180W请求对照。它不是执行方案中每一条严格统计步骤的完整实现。下表以实际保存的文件为准，说明主要边界。")
    report.table(["边界", "实际情况", "对结论的影响"], [
        ["基准与重复", "两次相同基准启动的速度差较大；多数候选每题只有一次，未完成计划中的每个候选3对交错重复。", "可以保守地不晋级；不能断言某参数普遍降低了多少性能。"],
        ["Agent题库修订", "最终12题由题目澄清后的指定复测与未受影响的首轮合成，原始失败保留。", "最终通过只对应修订后的契约；不是从始至终一次全通过。"],
        ["采样与代理", "归档含Hermes轨迹和结果事件，但本执行器没有保存计划中的统一逐请求代理记录，也没有显式冻结所有Agent采样字段。", "不能宣称拥有完整逐请求匹配的严格采样对照。"],
        ["长上下文覆盖", "会话切换验证了32K/128K；没有归档计划中的全部0.5K/2K/8K真实工具输出追加、240K回归与完整Agent功耗对照。", "不把短工具题的通过率推广到所有超长Agent场景。"],
        ["MTP后续候选", "已测布局、batch开关、spec-min-p=0.30/0.50/0.70；未完成spec=2/3/4窗口全扫或hnorm其他模式比较。", "本轮不是MTP全局优化；未确认路径的batch结果保持待验证。"],
        ["缓存归档", "128K切换有完整JSON；32K开启值只有控制台观察已写入汇总。", "两者的证据级别明确区分。"],
        ["判分覆盖", "T3未穷尽输入合法性与非变异契约；T6判分只覆盖最终JSON/DB，续接状态单列。", "12/12表示现有判分器通过，不等于所有任务契约已经形式化验证。"],
        ["硬件可靠性", "保存的最终核验中boot ID一致，未记录夜间VM重启；没有据此证明之前的CPU报错已根治。", "换回7282后的平台属于新阶段，需要单独建立基准。"],
    ])
    report.p("如果后续继续实验，应优先选真实使用中最明显的一个问题：例如多长任务切换时的缓存命中、或220W功耗折中；先把重复与记录做扎实，再增加候选数量。只有在同一模型、同一输入、同一测法下，才能把新成绩与本文直接对照。")

    report.section("closure", "13. 测试结束时保留了什么，以及后续硬件变更")
    report.table(["项", "2026-10-20 凌晨收尾状态"], [
        ["最终配置", "原始B0；prefill auto:8192；prefill-pipe=0；spec-min-p=0.50；workers=15；pipeline-windows=2；layer-split=auto；会话缓存0。"],
        ["GPU", "两张2080 Ti各250W；2070 SUPER为215W；nvidia-power-limit.service为disabled / inactive。"],
        ["服务核验", "2026-10-20 04:21:46（Asia/Shanghai）：health=ok、loaded=true，配置SHA与基准相符，实际进程与功耗核验通过。"],
        ["运行状态", "最终可用内存约31GiB；两张文本卡空闲温度48℃、52℃。这是收尾快照，不是随后关机或换CPU后的实时状态。"],
        ["重启记录", "最终boot ID为7125f2f0-fd2e-41f3-a43a-2d350a84eb03；夜间记录未显示VM重启。"],
        ["后续用户操作", "用户在阅读报告后计划关机，将AMD EPYC 7452换回7282。本文改写只使用本地归档，不重启服务、不尝试连接已关机机器、不补跑任何性能测试。"],
    ])
    report.p("当前证据支持保留原始引擎参数，同时把8GiB会话缓存视为面向多长会话切换的可选配置。是否长期使用180W则是延迟与能耗的偏好选择。此次没有出现足以据此购买新CPU或内存的性能证据。")

    report.section("archive", "附录：实验顺序、文件与复现入口")
    chronological = [(d['started'], ARM_NAMES[name], f"micro/{name}/results.json") for name,d in arms.items()]
    for sub in ("cache/CACHE8192/results.json", "cache/B0CACHE0/results.json", "power/results.json"):
        d = load(OUT / sub)
        chronological.append((d['started'], "功耗对照" if sub.startswith('power') else "会话切换缓存专项", sub))
    report.table(["开始时间（Asia/Shanghai）", "实验", "原始记录"], [
        [stamp.replace('T',' ').split('.')[0], title, link("JSON", path)] for stamp,title,path in sorted(chronological)])
    report.table(["证据", "用途"], [
        [link("原始夜间执行方案", "../Strata-Hermes-夜间调优执行方案-20261020.md"), "查看事先提出的问题和门槛；实际执行差异已在本报告逐项说明。"],
        [link("acceptance.json", "acceptance.json"), "保留原自动决策、逐题耗时、缓存与功耗汇总；本次不改写它的完成时间和历史结论。"],
        [link("final-verification.json", "final-verification.json"), "收尾健康、进程命令、环境、配置SHA、GPU上限和boot ID。"],
        [link("完整原始基准服务配置", "final-config.json"), "模型文件、参数、环境、视觉设置与GPU顺序。"],
        [link("suite-manifest.json", "suite-manifest.json"), "套件源码SHA256、数据种子和最终题目清单。"],
        [link("离线任务样例说明", "task-examples/README.md"), "含12次执行的重建输入、原始提示词和控制器标准答案；非原始远端快照。"],
        [link("任务样例manifest", "task-examples/manifest.json"), "样例文件哈希与重建源码哈希。"],
        [link("Agent逐题CSV", "pairwise.csv"), "机器可读的最终12题耗时对照。"],
        [link("冷请求逐条CSV（本版补充）", "micro-request-details.csv"), "不混合长度和题型；含输入/输出、复用、prefill、decode与客户端耗时。"],
        [link("旧版合并微测CSV", "micro-summary.csv"), "历史汇总原样保留；包含跨题型/长度合并中位数，不作为新版主表。"],
        [link("实际Agent执行器", "../../work/hermes-bench/nightly_suite.py"), "任务生成、Hermes调用、产物校验和续接记录的实现。"],
        [link("冷请求脚本", "../../work/hermes-bench/run_micro_arm.py"), "启动参数、一次64token预热、请求字段和逐项计时。"],
        [link("会话缓存脚本", "../../work/hermes-bench/cache_probe.py"), "A→B→A→B协议与reused记录。"],
        [link("功耗脚本", "../../work/hermes-bench/power_compare.py"), "功耗切换次序、采样和能量估计方法。"],
    ])
    report.p("Hermes远端原始轨迹保留在 `/home/hermes/strata-bench/strata-hermes-20261020-0200/`。本文仅使用已经保存到本地的文件；远端此刻是否在线不影响阅读和重建任务材料。图表的独立SVG保存在本报告同目录的figures文件夹。", "note")
    columns = ["arm", "label", "repeat", "prompt_tokens", "output_tokens", "prefix_reused", "prefill_tok_s", "decode_tok_s", "stream_first_s", "first_text_s", "wall_s", "draft_accept_rate"]
    with (OUT / "micro-request-details.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for name in ARM_ORDER:
            for row in arms[name]["rows"]:
                writer.writerow({"arm": name, **{k:row.get(k) for k in columns if k!='arm'}})
    report.finish(f"原始结果完成：{a['finished']}；本版整理：2026-10-20。参数与任务源于归档文件，未重新测试。")
    for path, before in untouched.items():
        if digest(path) != before:
            raise RuntimeError("Historical evidence was modified: " + str(path))
    print(pretty({"status": "rendered", "reports": ["夜间测试报告.html", "夜间测试报告.md"],
                  "arms": len(arms), "micro_requests": len(details_rows), "agent_cases": len(agent_rows),
                  "task_examples": len(task_examples), "historical_acceptance_and_verification_unchanged": True}))


if __name__ == "__main__":
    main()
