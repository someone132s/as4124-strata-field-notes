from __future__ import annotations

import base64
import csv
import datetime as dt
import hashlib
import html
import json
import math
import statistics as st
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Circle, Drawing, Line
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parent
CAMPAIGN = json.loads((ROOT / 'campaign.json').read_text(encoding='utf-8'))
ARMS = {a['id']: a for a in CAMPAIGN['arms']}
COLORS = {'A': '#2563eb', 'B': '#0d9488', 'author': '#ea780f', 'old': '#94a3b8', 'q4': '#8b5cf6'}
NAMES = {'A': '本机 A · auto:16384', 'B': '本机 B · auto', 'author': '7945 作者 · 新曲线',
         'old': '7945 作者 · 图中旧基线', 'q4': '2690v4 网友 · Q4_K_L/XL'}
METRICS = {
    'prefill': ('Prefill · 引擎速率', 'tok/s', 3000),
    'decode': ('Decode · 引擎纯生成速率', 'tok/s', 205),
    'ttft': ('首字延迟 · 客户端墙钟', 'seconds', 260),
    'api_prefill': ('Prefill · 输入 token / TTFT', 'tok/s', 2800),
    'accept': ('草稿接受率 · 口径见说明', '%', 100),
}


def median(values):
    return st.median(values)


def local_series(key, arm_id):
    arm = ARMS[arm_id]
    assert arm['status'] == 'completed' and len(arm['points']) == 6
    result = []
    for point in arm['points']:
        assert len(point['runs']) == 3
        rows = []
        for run in point['runs']:
            b, u = run['backend'], run['usage']
            assert b['reused'] == 0 and u.get('prompt_tokens_details', {}).get('cached_tokens', 0) == 0
            assert run['payload_sha256'] and u['completion_tokens'] > 0
            offered, accepted = b['drafts_offered'], b['drafts_accepted']
            rows.append({
                'series': key, 'length': point['label'], 'repeat': run['repetition'],
                'prompt_tokens': u['prompt_tokens'], 'output_tokens': u['completion_tokens'],
                'prefill': b['prompt_read'] / (b['prompt_ms'] / 1000),
                'decode': b['decode_tok_s'], 'ttft': run['ttft_s'],
                'api_prefill': u['prompt_tokens'] / run['ttft_s'],
                'accept': accepted / offered * 100,
                'drafts_offered': offered, 'drafts_accepted': accepted,
                'hit_rate': b['hit_rate'] * 100,
                'wall_s': run['wall_s'], 'e2e_output_tps': u['completion_tokens'] / run['wall_s'],
                'finish_reason': run['finish_reason'], 'reused_tokens': b['reused'],
                'payload_sha256': run['payload_sha256'],
            })
        p = {'label': point['label'], 'x': median(r['prompt_tokens'] for r in rows),
             'x_kind': 'actual_prompt_tokens_median', 'repetitions': 3, 'rows': rows,
             'output': median(r['output_tokens'] for r in rows),
             'wall_s': median(r['wall_s'] for r in rows),
             'hit_rate': median(r['hit_rate'] for r in rows),
             'accept_weighted': sum(r['drafts_accepted'] for r in rows) / sum(r['drafts_offered'] for r in rows) * 100}
        for metric in METRICS:
            vals = [r[metric] for r in rows]
            p[metric], p[metric + '_min'], p[metric + '_max'] = median(vals), min(vals), max(vals)
        assert abs(p['prefill'] - point['median_prefill_tps']) < 0.01
        assert abs(p['decode'] - point['median_decode_tps']) < 0.01
        result.append(p)
    return result


SERIES = {'A': local_series('A', 'A-prefill16384'), 'B': local_series('B', 'B-prefill-auto')}
for a, b in zip(SERIES['A'], SERIES['B']):
    for ra, rb in zip(a['rows'], b['rows']):
        assert ra['payload_sha256'] == rb['payload_sha256']
        assert ra['prompt_tokens'] == rb['prompt_tokens']

# S2: manually transcribed from the full-context chart supplied with the 7945 author's PDFs.
lengths = [.5, 1, 2, 4, 8, 16, 32, 64, 128, 192, 230]
new_prefill = [360.1, 506.8, 629.8, 853.1, 1264.6, 1351.7, 1858.3, 2308.6, 2575.2, 2631.6, 2667.8]
old_prefill = [346.1, 483.4, 491.4, 851.7, 1192.9, 1267.1, 1739.5, 2146.2, 2390.1, 2430.5, 2449.3]
new_decode = [179.8, 181.0, 168.7, 179.9, 176.0, 167.5, 156.0, 154.4, 151.6, 151.1, 148.8]
old_decode = [161.6, 166.7, 165.9, 160.3, 163.3, 157.1, 147.8, 144.4, 140.1, 136.6, 134.4]
for key, pf, dec in [('author', new_prefill, new_decode), ('old', old_prefill, old_decode)]:
    SERIES[key] = [dict(label=f'{n:g}K', x=n * 1024, x_kind='nominal_label_K_assumed_1024',
                        prefill=p, decode=d) for n, p, d in zip(lengths, pf, dec)]

# S4: this table belongs to the single 2690v4 commenter, NOT the PDF/7945 author.
q4_rows = [
    ('0.5K', 502, 2.17, 232, 236, 86.8, 90.8, 81.3),
    ('4K', 4215, 4.94, 854, 860, 80.5, 83.7, 78.3),
    ('32K', 33603, 19.85, 1691, 1695, 76.4, 79.2, 79.0),
    ('128K', 134328, 56.74, 2351, 2355, 71.1, 73.5, 80.4),
    ('230.6K', 241926, 97.72, 2476, 2480, 69.8, 72.5, 79.0),
]
SERIES['q4'] = [dict(label=label, x=x, x_kind='actual_prompt_tokens_from_screenshot', ttft=t,
                     api_prefill=pa, prefill=pe, api_decode=da, decode=de, accept=ac)
                for label, x, t, pa, pe, da, de, ac in q4_rows]

PDF_REFERENCE = [
    {'label': '32K', 'new_prefill_approx': 1820, 'new_decode_approx': 157,
     'old_prefill_range': [1720, 1760], 'old_decode_approx': 149},
    {'label': '128K', 'new_prefill_approx': 2570, 'new_decode_approx': 155,
     'old_prefill_range': [2390, 2390], 'old_decode_approx': 142},
    {'label': '230K', 'new_prefill_approx': 2670, 'new_decode_approx': 152,
     'old_prefill_range': [2390, 2450], 'old_decode_approx': 138},
]


def fmt(n, places=1):
    if n is None:
        return '—'
    return f'{n:,.{places}f}'


def esc(v):
    return html.escape(str(v))


def table(headers, rows, cls=''):
    return '<div class="table-scroll"><table class="' + cls + '"><thead><tr>' + ''.join(
        '<th>' + h + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join('<td>' + str(c) + '</td>' for c in r) + '</tr>' for r in rows) + '</tbody></table></div>'


def image_data(name):
    path = ROOT / 'sources' / name
    return 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()


CHART_DIR = ROOT / 'charts'
CHART_DIR.mkdir(exist_ok=True)


def chart(metric, keys, scope, y_override=None):
    width, height = 1100, 395
    drawing = Drawing(width, height)
    plot = LinePlot()
    plot.x, plot.y, plot.width, plot.height = 72, 56, 995, 310
    active = [(k, [p for p in SERIES[k] if metric in p]) for k in keys]
    active = [(k, pts) for k, pts in active if pts]
    plot.data = [[(p['x'], p[metric]) for p in pts] for k, pts in active]
    plot.xValueAxis.valueMin, plot.xValueAxis.valueMax = 0, 270000
    plot.xValueAxis.valueSteps = [0, 32768, 65536, 131072, 196608, 235520, 262144]
    plot.xValueAxis.labelTextFormat = lambda v: f'{v / 1024:g}K' if v else '0'
    plot.xValueAxis.labels.fontName = 'Helvetica'
    plot.xValueAxis.labels.fontSize = 11
    plot.yValueAxis.labels.fontName = 'Helvetica'
    plot.yValueAxis.labels.fontSize = 11
    ymax = y_override or METRICS[metric][2]
    plot.yValueAxis.valueMin, plot.yValueAxis.valueMax = 0, ymax
    step = 500 if ymax >= 2800 else 50 if ymax >= 200 else 20
    if scope == 'local' and metric == 'prefill':
        step = 300
    plot.yValueAxis.valueSteps = list(range(0, int(ymax) + 1, step))
    for axis in (plot.xValueAxis, plot.yValueAxis):
        axis.strokeColor = colors.HexColor('#a9b5c6')
        axis.labels.fillColor = colors.HexColor('#52617a')
        axis.visibleGrid = 1
        axis.gridStrokeColor = colors.HexColor('#e9eef5')
        axis.gridStrokeWidth = .6
    for i, (key, _) in enumerate(active):
        plot.lines[i].strokeColor = colors.HexColor(COLORS[key])
        plot.lines[i].strokeWidth = 2 if key == 'old' else 2.7
        if key == 'old':
            plot.lines[i].strokeDashArray = [5, 4]
    drawing.add(plot)
    markers = []
    for key, pts in active:
        color = colors.HexColor(COLORS[key])
        for p in pts:
            x = plot.x + p['x'] / 270000 * plot.width
            y = plot.y + p[metric] / ymax * plot.height
            if key in ('A', 'B'):
                lo = plot.y + p[metric + '_min'] / ymax * plot.height
                hi = plot.y + p[metric + '_max'] / ymax * plot.height
                drawing.add(Line(x, lo, x, hi, strokeColor=color, strokeWidth=.8))
                drawing.add(Line(x - 3, lo, x + 3, lo, strokeColor=color, strokeWidth=.8))
                drawing.add(Line(x - 3, hi, x + 3, hi, strokeColor=color, strokeWidth=.8))
            drawing.add(Circle(x, y, 3.7, fillColor=color, strokeColor=colors.white, strokeWidth=.8))
            markers.append(f'{NAMES[key]} · {p["label"]} · input {p["x"]:,.0f} tokens\n'
                           f'{METRICS[metric][0]}: {p[metric]:,.2f} {METRICS[metric][1]}')
    raw = renderSVG.drawToString(drawing)
    root = ET.fromstring(raw)
    ns = '{http://www.w3.org/2000/svg}'
    root.set('viewBox', f'0 0 {width} {height}')
    root.set('role', 'img')
    root.set('aria-label', METRICS[metric][0])
    for node, title in zip(root.iter(ns + 'circle'), markers):
        ET.SubElement(node, ns + 'title').text = title
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    svg = ET.tostring(root, encoding='unicode')
    (CHART_DIR / f'{metric}-{scope}.svg').write_text(svg, encoding='utf-8')
    return svg


LEGEND = '<div class="legend">' + ''.join(
    f'<span><i style="background:{COLORS[k]}"></i>{NAMES[k]}</span>' for k in ['A', 'B', 'author', 'old', 'q4']) + '</div>'
CHARTS = ''
descriptions = {
    'prefill': '本机按实际读取 token ÷ 引擎 prompt_ms 计算；两位网友采用各自图中的“引擎”列。竖线是本机三次的最小—最大值，不是置信区间。',
    'decode': '纯生成速率，不含读入 prompt。7945 曲线的任务形状与高草稿接受率不同，不能把跨机差距直接换算成 CPU 升级收益。',
    'ttft': '本机为客户端流式首个非空增量；2690v4 为截图 TTFT。7945 作者没有逐档实测 TTFT，留空；没有用输入/prefill 倒推一条“实测”首字曲线。',
    'api_prefill': '本机按每次 prompt_tokens / TTFT 再取中位数；2690v4 采用表内 TTFT 口径列。它包括首字前开销，和引擎 prefill 分开画。',
    'accept': '本机按 accepted/offered ×100 逐次计算后取中位数；2690v4 的接受率原样抄录，分母定义未提供。7945 图只给出约 98.3–98.9% 的总体区间，不能伪造逐点数值，所以不画该线。',
}
for metric in METRICS:
    overview = chart(metric, ['old', 'author', 'q4', 'A', 'B'], 'all')
    local = chart(metric, ['A', 'B'], 'local', 1650 if metric == 'prefill' else 85 if metric == 'decode' else None)
    CHARTS += f'<article class="chart"><div class="chart-head"><h3>{METRICS[metric][0]}</h3><span>{METRICS[metric][1]}</span></div>'
    CHARTS += f'<div class="plot all">{overview}</div><div class="plot local" hidden>{local}</div>'
    CHARTS += f'<div class="axis-note">输入 token（K=1024；本机和2690v4用实际计数；7945图只有标称档位）</div><p>{descriptions[metric]}</p></article>'

ab_rows = []
for a, b in zip(SERIES['A'], SERIES['B']):
    ab_rows.append([a['label'], fmt(a['x'], 0), fmt(a['prefill']), fmt(b['prefill']),
                    f'{(b["prefill"] / a["prefill"] - 1) * 100:+.1f}%',
                    fmt(a['decode']), fmt(b['decode']), f'{(b["decode"] / a["decode"] - 1) * 100:+.1f}%',
                    f'{a["ttft"]:.1f} / {b["ttft"]:.1f}', f'{a["output"]:.0f} / {b["output"]:.0f}'])
AB_TABLE = table(['档位', '实际输入中位数', 'A prefill', 'B prefill', 'B/A', 'A decode', 'B decode', 'B/A', 'TTFT A/B (s)', '输出 A/B'], ab_rows)

nearest_rows = []
for label, qindex in [('32K', 2), ('128K', 3), ('230K', 4)]:
    b = next(p for p in SERIES['B'] if p['label'] == label)
    au = next(p for p in SERIES['author'] if p['label'] == label)
    q = SERIES['q4'][qindex]
    nearest_rows.append([label, f'{b["prefill"]:.0f} / {b["decode"]:.1f}',
                         f'{au["prefill"]:.0f} / {au["decode"]:.1f}',
                         f'{au["prefill"]/b["prefill"]:.2f}× / {au["decode"]/b["decode"]:.2f}×',
                         f'{q["x"]:,} (+{(q["x"]/b["x"]-1)*100:.1f}%)',
                         f'{q["prefill"]:.0f} / {q["decode"]:.1f}',
                         f'{q["prefill"]/b["prefill"]:.2f}× / {q["decode"]/b["decode"]:.2f}×'])
NEAREST_TABLE = table(['相近档位', '本机 B 预填充/解码', '7945 新曲线', '7945 / 本机 B', '2690v4 实际输入 / 长度差', '2690v4 引擎速率', '2690v4 / 本机 B'], nearest_rows)

local_accept = [p['accept'] for key in ['A', 'B'] for p in SERIES[key]]
best_prefill = max(p['prefill'] for p in SERIES['B'])
ratio128 = SERIES['author'][8]['decode'] / SERIES['B'][2]['decode']
ratio230prefill = SERIES['author'][-1]['prefill'] / SERIES['B'][4]['prefill']
output_counts = [r['output_tokens'] for key in ['A', 'B'] for p in SERIES[key] for r in p['rows']]

param_rows = [
    ['来源身份', '本机 GPU VM，实测', '同左，仅 prefill CLI 不同', '两份 PDF + 配套全长图作者', '新评论 + 新测速截图；另一人'],
    ['CPU', '宿主双 EPYC 7282；虚拟机运行', '同 A', 'Ryzen 9 7945HX（硬件图）', '单路 2690v4（评论）'],
    ['内存', 'VM 历史配置128 GiB；宿主8×32GB；SMBIOS 3200 MT/s，未测带宽', '同 A', '硬件图96GB DDR5-4800；PDF另写92GB；称约77GB/s', '128GB DDR4-2400；无带宽计数'],
    ['GPU', '2×RTX 2080 Ti 22GB', '同 A', '2×RTX 2080 Ti 22GB；图注250W', '2×RTX 2080 Ti 22GB；称占43G'],
    ['PCIe / 链路', '历史探测约9.5–10.2 GB/s；本轮未复测链路宽度', '同左', 'Gen3 x8+x8；硬件图有NVLink桥，是否用于该路径未独立核实', '未提供'],
    ['权重', 'Swift-1.5 abl. IQ3_S + 外部Q8_0 PLE', '同 A', 'ISTA-DASLab Qwen3.8-Flash-Next GSQ-RCO IQ3_S + 随包PLE', '标题Q4kxl；正文ud-q4-k-l；具体GGUF身份待核实'],
    ['引擎 / 构建', '0.1.43.1；本轮运行元数据', '同 A', '新：0.1.43 + sm75批次补丁（9 PR）；旧PDF：0.1.40.3；图中旧线：0.1.40.1', '未提供版本、提交或补丁'],
    ['并发 / batch', 'parallel=1；batch关闭', '同 A', '图/文档为单请求串行；不等于batch=2', '未给出并发和batch设置'],
    ['--layer-split', '26', '26', '26', '未提供'],
    ['--pipeline-windows', '2', '2', '2', '评论称2必须开，完整启动参数缺失'],
    ['--prefill', 'auto:16384', 'auto；历史/代码默认8192，本campaign无实际chunk字段', 'auto:16384', '未提供'],
    ['--spec / --spec-min-p', '4 / 0.70（CLI）', '同 A', '4 / 0.70', '未提供'],
    ['MTP / hnorm', '随部署MTP；--mtp-hnorm stream', '同 A', '随包MTP；hnorm未明确', '未提供；截图有接受率'],
    ['KV / 驻留', 'int8 / 32768', '同 A', 'int8 / 32768', '未提供'],
    ['最大上下文', '262144', '同 A', '262144', '截图最大实际prompt 241926；最大配置未提供'],
    ['会话停泊缓存', '16384 MiB / 12 slots', '同 A', '新PDF：16384 MiB / 12 slots；早期硬件图：8192 MiB / 4 slots', '称8会话共16G；包含在90G系统内存中'],
    ['显存预留', '700 / 700 MiB', '同 A', '700 MiB；第二卡未单独给出', '未提供'],
    ['专家显存缓存', '18152 slots / 35394 MiB', '18152 slots / 35394 MiB', '无可直接对应的逐档数据', '未提供；总显存占用43G不能等同专家缓存'],
    ['运行时 PCIe fraction', '0.25（auto探测）', '0.27（auto探测）', '未提供', '未提供'],
    ['arena / 启动空余', '26223 MiB / 497 MiB', '20066 MiB / 511 MiB', '未提供同口径值', '未提供'],
    ['worker / aux', '15 / aux关闭', '同 A', '未提供', '未提供'],
    ['BF16_TC / STAGE_TRIM', '1 / 1（脚本显式设置）', '同 A', 'BF16_TC=1；STAGE_TRIM未说明', '评论称BF16_TC要开；其余未给'],
    ['作者特有环境变量', '未在本campaign逐一核验，不能假设与作者一致', '同 A', '新版：SELECT_SIMT=2、PA_V2T=1、REFILL_PARTS=1、PREFILL_HELP=1；旧版：SELECT_SIMT=1', '未提供'],
    ['视觉', '关闭', '关闭', '服务开启，CPU编码；该图用纯文本请求', '评论展示图像任务；测速表是否同次含图未说明'],
    ['请求 / 输出', f'随机20词词表分析；cap1000；实际{min(output_counts)}–{max(output_counts)} tokens；禁思考', '同文本/同payload hash；输出实际长度有变化', '配套图标1000-token生成；PDF三点值写2600-token计数任务', 'prompt计数已给；任务文本、输出长度、采样未给'],
    ['重复 / 汇总', '每组先2次单token长度校准；每档3次均计入，中位数及min–max', '同 A；先A后B，非交错随机顺序', '全长图逐点次数未说明；补丁贡献另称2次均值；PDF三点称2次均值', '每档仅截图一行，重复次数不详'],
]
PARAM_TABLE = table(['项目', '本机 A', '本机 B', '7945 / PDF作者', '2690v4 / 新网友'], param_rows, 'params')

own_detail = []
for key in ['A', 'B']:
    for p in SERIES[key]:
        own_detail.append([key, p['label'], fmt(p['x'], 0), fmt(p['output'], 0),
                           fmt(p['prefill']), fmt(p['api_prefill']), fmt(p['decode']),
                           fmt(p['ttft'], 2), fmt(p['wall_s'], 2), fmt(p['accept']), fmt(p['hit_rate'])])
OWN_TABLE = table(['组', '档位', '实际prompt', '实际输出', 'prefill引擎', 'prefill客户端', 'decode引擎', 'TTFT s', '总耗时 s', '草稿接受%', '专家命中%'], own_detail)
Q4_TABLE = table(['截图档位', '实际prompt', 'TTFT s', 'prefill TTFT/引擎', 'decode API/引擎', '接受率'],
                 [[p['label'], f'{p["x"]:,}', fmt(p['ttft'], 2), f'{p["api_prefill"]:,} / {p["prefill"]:,}',
                   f'{p["api_decode"]:.1f} / {p["decode"]:.1f}', f'{p["accept"]:.1f}%'] for p in SERIES['q4']])
AUTHOR_TABLE = table(['标称输入', '新prefill', '旧prefill', '新decode', '旧decode'],
                     [[a['label'], fmt(a['prefill']), fmt(o['prefill']), fmt(a['decode']), fmt(o['decode'])]
                      for a, o in zip(SERIES['author'], SERIES['old'])])
PDF_TABLE = table(['档位', '新版PDF约值 预填充/解码', '旧版PDF约值 预填充/解码'],
                 [[p['label'], f'{p["new_prefill_approx"]} / {p["new_decode_approx"]}',
                   f'{p["old_prefill_range"][0]}–{p["old_prefill_range"][1]} / {p["old_decode_approx"]}'] for p in PDF_REFERENCE])

SHORT_TABLE = table(['本机短程调度组', '课本prefill tok/s（加权）', '课本decode中位数', 'TTFT中位数 s'],
                    [[esc(a['id']), fmt(a['book']['summary']['prefill_weighted_tps']),
                      fmt(a['book']['summary']['decode_median_tps']), fmt(a['book']['summary']['ttft_median_s'], 2)]
                     for a in CAMPAIGN['arms'][:4]])

COMMENT = '''双2080TI跑3.8-FLASH-NEXT-Q4kxl
配置：单路2690v4+128g-ddr4-2400+2080ti22g*2；路线strata；模型ud-q4-k-l；显存占用43G，内存占用90G（含8个会话停泊共16G）。
评论称：会话停泊要开4以上不然dsh缓存命中为0；pipeline-windows-2要开；bf16-tc要开，还有其他一些；开启后prefill从1000翻倍到2000。
本记录由用户于2026-10-15粘贴提供，测速表属于此2690v4网友，不属于两份PDF的7945作者。没有提供该帖URL、完整启动配置或原始请求日志。
'''
(ROOT / 'sources' / '2690v4-网友评论.txt').write_text(COMMENT, encoding='utf-8')

CSS = '''
:root{--ink:#182941;--muted:#60728c;--line:#dfe6f0;--bg:#f3f6fa;--blue:#2563eb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 "Segoe UI","Microsoft YaHei",sans-serif}
header{background:#14243c;color:white;padding:42px max(24px,calc((100vw - 1220px)/2)) 35px}header .kicker{color:#9dbbea;font-size:12px;letter-spacing:.13em}
h1{font-size:34px;line-height:1.3;margin:12px 0}header p{color:#c6d3e6;max-width:1000px;margin:8px 0}main{max-width:1268px;margin:auto;padding:24px}
.chips,.legend{display:flex;gap:12px;flex-wrap:wrap}.chip{font-size:12px;border:1px solid #52617a;border-radius:30px;padding:3px 11px;color:#d9e4f2}
section,.chart{background:white;border:1px solid var(--line);border-radius:14px;padding:24px;margin-bottom:20px}h2{font-size:23px;margin:0 0 12px}h3{font-size:18px;margin:0}p{margin:8px 0 14px}.muted,.small{color:var(--muted)}.small{font-size:12px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}.card{padding:20px;background:white;border:1px solid var(--line);border-radius:12px}.card strong{display:block;font-size:29px;line-height:1.2;margin:8px 0}.card span{font-size:12px;color:var(--muted)}
.callout{border-left:4px solid #db8a20;background:#fff8e8;padding:14px 18px;border-radius:6px;margin:16px 0}.good{border-color:#0d9488;background:#eefaf6}
.toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:14px 0 18px}button,.linkbtn{background:white;border:1px solid #bfcde0;color:var(--ink);padding:8px 13px;border-radius:8px;cursor:pointer;font:inherit;font-size:13px}button.active{background:#1d4ed8;border-color:#1d4ed8;color:white}
.legend{font-size:12px;gap:9px 20px;color:#52617a;margin:12px 0}.legend i{display:inline-block;width:22px;height:3px;vertical-align:middle;margin-right:6px}.chart-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.chart-head span{font-size:12px;color:var(--muted)}
.plot{width:100%;margin-top:8px}.plot svg{width:100%;height:auto}.plot[hidden]{display:none}.axis-note{text-align:center;color:var(--muted);font-size:12px}.chart p{font-size:13px;color:var(--muted);margin:14px 0 0}
.table-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:8px;margin:14px 0}table{border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap}th{background:#edf2f8;text-align:left;color:#455873;font-weight:600}th,td{border-bottom:1px solid #e8edf4;padding:10px 12px;vertical-align:top}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#fafcfe}.params{white-space:normal;min-width:1100px;table-layout:fixed}.params th:first-child{width:145px}.params td:first-child{font-weight:600}.params td{line-height:1.6}
details{border-top:1px solid var(--line);padding-top:14px;margin-top:16px}summary{cursor:pointer;font-weight:600}details img{max-width:100%;height:auto;border:1px solid var(--line);margin-top:12px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}.grid2>div{min-width:0}ul{padding-left:22px}li{margin:7px 0}a{color:#1d4ed8}code{font:12px/1.5 Consolas,monospace;background:#edf2f8;border-radius:4px;padding:2px 5px}.tag{display:inline-block;font-size:11px;border:1px solid #cbd5e1;border-radius:20px;padding:1px 8px;margin-left:6px;color:#64748b}footer{color:var(--muted);font-size:12px;padding:0 4px 30px}.sources li{font-size:13px}
@media(max-width:850px){header{padding:28px 18px}h1{font-size:27px}main{padding:14px}.cards{grid-template-columns:1fr 1fr}.grid2{grid-template-columns:1fr}section,.chart{padding:17px}}
@media print{body{background:white}main{max-width:none;padding:0}header{padding:22px;color:#182941;background:white;border-bottom:2px solid #182941}header p,header .kicker{color:#52617a}.chips,.toolbar{display:none}section,.chart{break-inside:avoid;border:1px solid #ddd}.table-scroll{overflow:visible}.params{min-width:0;font-size:9px}.params th:first-child{width:90px}td,th{padding:5px}.cards{grid-template-columns:repeat(4,1fr)}a{color:inherit}}
'''

HTML = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Strata 长上下文实测对比 · 2026-10-15</title><style>{CSS}</style></head><body>
<header><div class="kicker">STRATA / LONG CONTEXT / EVIDENCE NOTE</div><h1>同为双 2080 Ti，差距在哪里？</h1><p>本机 A/B 长上下文实测 × 7945 作者的 PDF 配套曲线 × 2690v4 网友的 Q4 测速表。性能数值、测量口径和配置来源分别记录。</p><div class="chips"><span class="chip">2026-10-15 · 北京时间</span><span class="chip">本机 36 个长输入正式请求</span><span class="chip">32K → 约260000输入 tokens</span><span class="chip">自包含 HTML · 离线可用</span></div></header>
<main>
<div class="cards"><div class="card"><span>本机 B 的最高 prefill 中位数</span><strong>{best_prefill:,.0f}</strong><span>tok/s · 64K 档 · 引擎口径</span></div><div class="card"><span>128K：7945 新图 / 本机 B decode</span><strong>{ratio128:.2f}×</strong><span>151.6 对 57.7 tok/s · 跨机参考</span></div><div class="card"><span>230K：7945 新图 / 本机 B prefill</span><strong>{ratio230prefill:.2f}×</strong><span>2667.8 对 1185.7 tok/s</span></div><div class="card"><span>本机 B near-256K 首字中位数</span><strong>{SERIES['B'][-1]['ttft']:.1f}s</strong><span>259969 实际输入 tokens · 非缓存请求</span></div></div>

<section><h2>先读这三个判断</h2>
<p><b>本机长输入的主要新现象，是 prefill 在约64K见顶，此后回落；decode 则维持约55–60 tok/s。</b> 相比之下，7945 作者的 prefill 随输入变长提升到约2.67K tok/s，decode 保持约149 tok/s。我们缺少的是整段吞吐曲线，不只是短 prompt 的首请求成绩。</p>
<p><b><code>auto</code> 对短一些的长输入有优势，但 <code>auto:16384</code> 也没有在超长段翻盘成大幅提升。</b> B 在32K/64K的 prefill 分别比A高13.7%/7.3%；到 near-256K，B反而低3.5%。两组都已开 <code>pipeline-windows 2</code> 与 BF16_TC，不能把外部案例的差距直接解释为我们漏开了这两个开关。</p>
<p><b>2690v4 新表确实值得保留，但它属于另一台机器和另一种权重。</b> 在相近长输入下，其引擎 decode 为72.5–79.2 tok/s，位于本机IQ3结果与7945作者结果之间；prefill却接近7945作者。跨机观察支持继续查工作负载、版本/补丁、内核与传输路径，不足以分解CPU、内存、量化各自贡献。</p>
<div class="callout"><b>作者归属已按用户澄清：</b>两份PDF与配套全长曲线属于7945那位作者（硬件图标注7945HX）；新粘贴的TTFT/双口径速度表属于<b>单路2690v4</b>网友。后者的参数不会补写到前者身上。</div></section>

<section><h2>性能曲线</h2><p class="muted">横轴按实际 token 数对齐。作者的全长图未提供实际输入计数，暂按图标的K×1024放置；不外推作者在256K的值，也不填补未测点。把鼠标停在圆点上可查看数值。</p>
{LEGEND}<div class="toolbar"><button class="active" data-view="all" onclick="setView('all')">跨机总览</button><button data-view="local" onclick="setView('local')">仅本机 A/B · 放大纵轴</button><button onclick="window.print()">打印 / 另存 PDF</button><a class="linkbtn" href="comparison-data.json" download>下载数据 JSON</a></div>
<p class="small">本机竖线表示三次最小—最大值；每条曲线的圆点表示中位数。外部来源没有逐次原始数据，不画误差条。折线只连接测得点，不表示中间输入已测。</p></section>
{CHARTS}

<section><h2>本机 A/B：相同输入，主要变化是 prefill 配置</h2>{AB_TABLE}
<p class="small">prefill/decode单位均为tok/s。输出上限1000，但模型可提前停止，所以实际输出并不恒为1000；端到端耗时不能直接当成等输出量性能对照。</p>
<div class="callout"><b>仍有运行时混杂：</b>18组配对输入的payload hash和实际prompt计数全部相同，但启动自动探测的 PCIe fraction 为A=0.25、B=0.27；arena为26223/20066MiB，expert slots均为18152。顺序固定先A后B，每点仅3次。因此这些是本次配置的观测差异，不能把每个百分比都认定为单一chunk参数的因果收益。</div></section>

<section><h2>相近长度的直接读数</h2>{NEAREST_TABLE}<p class="small">所有速度为引擎prefill / 引擎decode。2690v4的相近点比本机多约2.5–2.7%输入；表内只是原始比值，没有插值、长度修正或硬件归一化。7945的实际prompt未知。</p>
<p>这组数据的意义是确定差距的形状：我们在长输入下同时落后于对方的读入速度和生成速度。要归因，仍须匹配模型/PLE、请求任务、草稿接受率及引擎构建；把它直接折算成“换某颗CPU就会快多少”没有依据。</p></section>

<section><h2>运行条件与参数逐项对照</h2>{PARAM_TABLE}
<p class="small">“未提供/未核验”是证据缺口，不等于默认值，也不等于没有启用。引擎元数据中的派生spec=6与CLI --spec 4同时保留，不视为参数失效。硬件、DIMM速率等历史记录不等于本轮性能计数器实测。</p></section>

<section><h2>如何理解 2690v4 网友的经验</h2>
<div class="grid2"><div><h3>可以从新表确认的</h3><ul><li>截图给出了真实prompt计数、TTFT、两种prefill/两种decode和接受率；本报告使用其<b>引擎列</b>做主图。</li><li>最长行标“230.6K”，实际prompt是<b>241926</b>，即236.3×1024；图上按实际计数放置，没有误贴到230×1024。</li><li>新表中引擎prefill最高2480 tok/s，decode随长度从90.8降到72.5 tok/s；两者趋势与本机不同。</li><li>Q4标题写Q4kxl，正文写ud-q4-k-l；没有精确文件名，暂不把它们当成已确认的相同GGUF。</li></ul></div>
<div><h3>仍不能直接推广的</h3><ul><li>“停泊槽必须4以上，否则DSH命中为0”是该作者使用路径中的经验。会话缓存/前缀复用、专家缓存命中、MTP接受率是三种不同统计；我们的fresh测试要求reused=0，不以DSH缓存命中为目标。</li><li>“开几个参数后prefill从1000翻倍到2000”没有单变量原始日志，不能拆成pipeline-windows或BF16_TC各自的收益。</li><li>本机已经开启BF16_TC；长A/B也已经开启pipeline-windows2。该评论提供参考部署，不构成本机缺少开关的证据。</li><li>约90G RAM含16G停泊、约43G显存是作者自述，未提供统计单位或逐项归属；不等同专家权重驻留量。</li></ul></div></div>
<details><summary>2690v4 原始截图与逐行抄录</summary><img src="{image_data('2690v4-网友测速表.png')}" alt="单路2690v4网友的测速表，与7945作者无关">{Q4_TABLE}<pre class="small" style="white-space:pre-wrap">{esc(COMMENT)}</pre></details></section>

<section><h2>为什么7945作者的160 tok/s不能直接当作同题成绩</h2>
<p>在本机，本轮是随机20词词表的分析任务，温度0、禁思考、输出cap1000；实际完成{min(output_counts)}–{max(output_counts)} tokens。PDF作者的配套图标注“1000-token生成”，但PDF性能章节使用“计数类请求2600生成tokens、两次均值”。任务和输出形状不同，会影响投机解码的可接受程度与平均生成速度。</p>
<p>本机各点草稿接受率中位数约<b>{min(local_accept):.1f}–{max(local_accept):.1f}%</b>；7945图称约<b>98.3–98.9%</b>。这是需要优先匹配的观测差别，但尚未隔离其来自任务形状、MTP资源、模型、实现或统计口径的比例。不能把命中率高或接受率高直接解释为模型更聪明。</p>
<p>另外，新版作者引擎是v0.1.43叠加sm75批次补丁；本机报告v0.1.43.1。相近版本号不能证明二进制等价。图中“补丁单独贡献”的+6%至+11%来自作者同机对照，它也不能解释或归因我们整段2–3倍的跨机差距。</p>
<details><summary>7945作者：配套图原始数据</summary><img src="{image_data('7945HX-作者全长曲线.png')}" alt="7945作者的全长性能曲线">{AUTHOR_TABLE}</details>
<details><summary>PDF三点参考值：与上图分开保留</summary>{PDF_TABLE}<p class="small">以上仅是PDF约值。新版PDF为2600-token计数请求、两次均值；旧PDF同为计数类长输出。没有把这些约值拼接进全长图曲线。图中旧基线日期2026-10-07、标注v0.1.40.1；旧PDF标注v0.1.40.3，二者也未合并为一个版本。</p></details>
<details><summary>7945作者：硬件配置原图</summary><img src="{image_data('7945HX-作者硬件配置.png')}" alt="7945HX作者的硬件与配置图"></details></section>

<section><h2>本机调度对照：给后续总吞吐结论留好边界</h2>{SHORT_TABLE}
<p>这些是每组两个预热、三个正式课本请求的<b>单请求读数</b>，不是两路总吞吐。当前batch和ring已有独立的双客户端结果；pipeline-windows2的匹配双客户端补测已获用户授权，尚未并入本报告。仅凭这里的66.0与61.9 tok/s，不能推荐单流或双并发。</p>
<p class="small">执行状态：原runner最后的恢复验收记录因“too many values to unpack (expected 2)”标记restore-failed；随后独立只读核查确认/health健康、IQ3已加载、两份配置hash与原始值一致。没有为核查额外重启。按当前监控停止条件，新增双客户端补测尚未触发；这不影响本报告36次已完成性能数据。见<a href="restore-verification.json">只读恢复核查记录</a>。</p></section>

<section><h2>原始数值与追溯</h2><details><summary>展开本机全部档位汇总</summary>{OWN_TABLE}</details>
<ul class="sources"><li><b>S1 · 本机原始性能元数据：</b><a href="campaign.json">campaign.json</a>。6档×3次×2组，全部fresh、无前缀复用；最终性能数据完整。原runner的恢复验收记录抛ValueError，保留原状；另存只读健康和hash核查证据。没有把“数据完整”写成“runner所有验收都通过”。</li>
<li><b>S2 · 7945作者配套曲线：</b>用户提供截图；新曲线v0.1.43+sm75批次补丁，旧基线2026-10-07。已逐点抄录到<a href="comparison-data.json">comparison-data.json</a>。</li>
<li><b>S3 · 两份PDF：</b>用户本地strata-deploy-guide-new.pdf及strata-deploy-guide.pdf，使用此前已提取文本。归档<a href="sources/page-01.txt">新版p1</a>、<a href="sources/page-05.txt">新版p5</a>、<a href="sources/page-06.txt">新版p6</a>、<a href="sources/page-07.txt">新版p7</a>、<a href="sources/old-guide-page-01.txt">旧版p1</a>、<a href="sources/old-guide-page-04.txt">旧版p4</a>。</li>
<li><b>S4 · 2690v4网友：</b>2026-10-15用户粘贴评论与测速截图；作者归属按用户随后澄清。见<a href="sources/2690v4-网友评论.txt">评论归档</a>。未提供原帖URL，标为社区自述，未由本机复测。</li>
<li><b>复现本报告：</b><a href="generate_report.py">Python生成器</a>、<a href="local-requests.csv">36次逐请求CSV</a>、<a href="comparison-data.json">结构化JSON</a>、<a href="charts/prefill-all.svg">prefill SVG</a>、<a href="charts/decode-all.svg">decode SVG</a>。HTML内嵌图表与原图，离线可读；这些下载链接需保留同目录。</li></ul>
<div class="callout good">接下来的解释顺序：先完成pipeline-windows2双客户端补测，回答本机单流/并发选择；再用相同任务和MTP资源比较外部曲线。当前没有服务调参或硬件采购结论被这份跨机图自动替代。</div></section>
<footer>图由 ReportLab LinePlot 生成，数据点悬停显示原始值。指标采用各来源实际可得口径；缺失字段保留为空。生成日期2026-10-15（Asia/Shanghai）。</footer></main>
<script>function setView(mode){{document.querySelectorAll('.plot.all').forEach(x=>x.hidden=mode!=='all');document.querySelectorAll('.plot.local').forEach(x=>x.hidden=mode!=='local');document.querySelectorAll('button[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===mode));}}</script></body></html>'''

(ROOT / 'Strata长上下文性能对比.html').write_text(HTML, encoding='utf-8')
DATA = {'generated_date': '2026-10-15', 'timezone': 'Asia/Shanghai',
        'sources': {'local': str(ROOT / 'campaign.json'), '7945': 'user-provided PDF companion chart; nominal x',
                    '2690v4': 'user-provided screenshot and comment; actual x'},
        'series_names': NAMES, 'series': SERIES, 'pdf_reference_points_separate_protocol': PDF_REFERENCE,
        'validation': {'local_requests': 36, 'paired_payload_hashes_equal': 18,
                       'local_reused_tokens': 0, 'source_campaign_sha256': hashlib.sha256((ROOT / 'campaign.json').read_bytes()).hexdigest()}}
(ROOT / 'comparison-data.json').write_text(json.dumps(DATA, ensure_ascii=False, indent=2), encoding='utf-8')
csv_rows = [r for key in ['A', 'B'] for p in SERIES[key] for r in p['rows']]
with (ROOT / 'local-requests.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]))
    writer.writeheader(); writer.writerows(csv_rows)
assert HTML.count('<article class="chart">') == 5
assert HTML.count('<svg') == 10
assert HTML.count('data:image/png;base64,') == 3
for svg_path in CHART_DIR.glob('*.svg'):
    ET.parse(svg_path)


class LinkAudit(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href') and not attrs['href'].startswith(('http', '#', 'data:')):
            assert (ROOT / attrs['href']).exists(), attrs['href']


LinkAudit().feed(HTML)
print('DATA_SVG_AND_LOCAL_LINK_VALIDATION_PASS')
print(json.dumps({'html': str(ROOT / 'Strata长上下文性能对比.html'), 'local_requests': len(csv_rows),
                  'A_points': len(SERIES['A']), 'B_points': len(SERIES['B']),
                  'best_B_prefill': best_prefill, 'local_accept_range': [min(local_accept), max(local_accept)],
                  'ratio128_decode_author_to_B': ratio128}, ensure_ascii=False, indent=2))
