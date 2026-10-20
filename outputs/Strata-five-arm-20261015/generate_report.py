import json, pathlib, html
ROOT=pathlib.Path('outputs/Strata-five-arm-20261015')
D=json.loads((ROOT/'campaign.json').read_text(encoding='utf-8'))
labels={
 'A-prefill16384':('A','--prefill auto:16384','固定上限提示值为16K'),
 'B-prefill-auto':('B','--prefill auto','默认自动策略'),
 'C-ring384':('C','auto:16384 + ring384','A组基础上设STRATA_SPLIT_RING=384'),
 'D-simt1':('D','auto:16384 + SIMT=1','A组基础上设STRATA_SELECT_SIMT=1'),
 'E-aux-auto':('E','auto:16384 + aux-cpus auto','A组基础上启用辅助CPU线程自动分配'),
}
rows=[]
for a in D['arms']:
    r=a['official']['results']; p=r['prompts']; g=r['agent']; b=a['book']['summary']; tag,name,note=labels[a['id']]
    rows.append({'id':a['id'],'tag':tag,'name':name,'note':note,
      'chat_decode':r['chat']['decode_tps']['median'],'chat_ttft':r['chat']['ttft_s']['median'],
      'p4':p['4K']['prompt_tps']['median'],'t4':p['4K']['ttft_s']['median'],
      'p16':p['16K']['prompt_tps']['median'],'t16':p['16K']['ttft_s']['median'],
      'p32':p['32K']['prompt_tps']['median'],'t32':p['32K']['ttft_s']['median'],
      'agent_decode':g['turn_decode_tps']['median'],'agent_ttft':g['turn_ttft_s']['median'],
      'book_decode':b['decode_median_tok_s'],'book_prefill':b['prefill_weighted_tok_s'],
      'book_ttft':b['ttft_median_s'],'book_e2e':b['end_to_end_tok_s'],'book_hit':b['expert_hit_rate_median']})
summary={'status':D['status'],'finished_local':D['finished_local'],'model':D['model'],'arms':rows,
'comparison_context':{'prior_official_parallel2_baseline':{'chat_decode':43.6,'chat_ttft':0.751,'p4':803,'t4':5.077,'p16':1251,'t16':12.963,'agent_decode':56.8,'agent_ttft':4.40,'two_client_total':37.56},
'prior_book_parallel2_hnorm':{'decode':61.3,'prefill':1248.17,'ttft':15.78,'e2e':31.76,'hit':0.985},
'prior_book_parallel2_aux':{'decode':65.5,'prefill':1276.98,'ttft':15.58,'e2e':32.82,'hit':0.984}},
'pre_sha':D['pre_run']['config_sha256'],'restored_sha':D['restored']['config_sha256'],'restore_status':D['restored']['status'],
'protocol':D['protocol'],'common_config':D['common_config']}
(ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
def fmt(v,n=1): return f'{v:.{n}f}'
# svg: single-panel prefill curve
W,H=920,390; left,right,top,bottom=72,28,30,60
xs=[left+ i*(W-left-right)/2 for i in range(3)]; y_min,y_max=600,1450
def y(v): return top+(y_max-v)*(H-top-bottom)/(y_max-y_min)
colors=['#4f46e5','#0f766e','#ea580c','#7c3aed','#0284c7']
svg=[f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="各组长prompt预填充速度">']
for v in range(600,1500,100):
    yy=y(v); svg.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{W-right}" y2="{yy:.1f}" stroke="#e5e7eb"/><text x="{left-12}" y="{yy+4:.1f}" text-anchor="end" fill="#64748b" font-size="12">{v}</text>')
for i,label in enumerate(['4K','16K','32K']):
    svg.append(f'<text x="{xs[i]:.1f}" y="{H-25}" text-anchor="middle" fill="#475569" font-size="14">{label}</text>')
for row,color in zip(rows,colors):
    vals=[row['p4'],row['p16'],row['p32']]; points=' '.join(f'{x:.1f},{y(v):.1f}' for x,v in zip(xs,vals))
    svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
    for x,v in zip(xs,vals): svg.append(f'<circle cx="{x:.1f}" cy="{y(v):.1f}" r="5" fill="{color}"/><text x="{x:.1f}" y="{y(v)-10:.1f}" text-anchor="middle" fill="{color}" font-size="11">{v:.0f}</text>')
svg.append(f'<text x="20" y="{(H-top-bottom)/2+top:.1f}" transform="rotate(-90 20 {(H-top-bottom)/2+top:.1f})" text-anchor="middle" fill="#475569" font-size="13">Prefill tok/s (中位数)</text>')
svg.append('</svg>')
legend=''.join(f'<span><i style="background:{c}"></i>{r["tag"]} {html.escape(r["name"])}</span>' for r,c in zip(rows,colors))
bench_rows=''.join('<tr><td><b>'+r['tag']+'</b> '+html.escape(r['name'])+'</td><td>'+fmt(r['chat_decode'])+'</td><td>'+fmt(r['chat_ttft'],3)+'</td><td>'+fmt(r['p4'])+' / '+fmt(r['t4'],2)+'s</td><td>'+fmt(r['p16'])+' / '+fmt(r['t16'],2)+'s</td><td>'+fmt(r['p32'])+' / '+fmt(r['t32'],2)+'s</td><td>'+fmt(r['agent_decode'])+' / '+fmt(r['agent_ttft'],2)+'s</td></tr>' for r in rows)
book_rows=''.join('<tr><td><b>'+r['tag']+'</b> '+html.escape(r['name'])+'</td><td>'+fmt(r['book_decode'])+'</td><td>'+fmt(r['book_prefill'])+'</td><td>'+fmt(r['book_ttft'],2)+'</td><td>'+fmt(r['book_e2e'])+'</td><td>'+fmt(r['book_hit']*100,1)+'%</td></tr>' for r in rows)
html_doc=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Strata 五组参数测试 | 2026-10-15</title><style>
:root{{--ink:#14202e;--muted:#5d6b7b;--line:#dbe3ec;--bg:#f3f6fa;--card:#fff;--blue:#2563eb;--green:#0f766e}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,"Microsoft YaHei",sans-serif}}header{{background:linear-gradient(120deg,#0f172a,#1e3a8a);color:white;padding:42px max(24px,calc((100vw - 1180px)/2)) 36px}}header h1{{margin:0 0 8px;font-size:32px}}header p{{margin:5px 0;color:#dbeafe}}main{{max-width:1180px;margin:24px auto;padding:0 20px 60px}}section,.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;margin:18px 0;box-shadow:0 5px 20px #10243b0a}}h2{{margin:0 0 14px;font-size:22px}}h3{{margin:22px 0 8px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.kpi{{border:1px solid var(--line);border-radius:12px;padding:15px}}.kpi strong{{display:block;font-size:23px;color:#1d4ed8}}.muted,small{{color:var(--muted)}}.pill{{display:inline-block;border-radius:999px;background:#dcfce7;color:#166534;font-weight:700;padding:3px 10px}}table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}th,td{{padding:10px 9px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}}th:first-child,td:first-child{{text-align:left}}th{{background:#f8fafc;color:#334155}}.scroll{{overflow:auto}}.legend{{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 12px}}.legend span{{display:flex;align-items:center;gap:6px;font-size:13px}}.legend i{{width:10px;height:10px;border-radius:50%;display:inline-block}}svg{{width:100%;height:auto}}.callout{{border-left:4px solid var(--blue);background:#eff6ff;padding:12px 16px;border-radius:5px}}.warn{{border-left-color:#d97706;background:#fffbeb}}code{{background:#edf2f7;padding:2px 5px;border-radius:4px}}@media(max-width:700px){{header h1{{font-size:25px}}section{{padding:16px}}}}</style></head><body>
<header><h1>Strata 五组参数测试</h1><p>Qwen3.8 Flash Next IQ3_S + Q8 PLE · 双 RTX 2080 Ti · Strata 0.1.43.1 · 2026-10-15</p><p><span class="pill">五组测试完成</span> 服务已恢复并验证为 EvalScope 双并发配置</p></header><main>
<section><h2>结果先看</h2><div class="cards"><div class="kpi"><strong>B · auto 最适合长输入</strong><span>16K / 32K prefill 中位数最高：1,165 / 1,379 tok/s；32K首字23.4秒。</span></div><div class="kpi"><strong>E · aux 改善4K/Agent</strong><span>官方4K prefill 833 tok/s、Agent decode 67.7 tok/s及首字4.04秒为五组最佳；课本decode 72.8 tok/s略高。</span></div><div class="kpi"><strong>C · ring 未复现普遍提升</strong><span>课本预填充926.9 tok/s，16K/32K官方prefill最低；未形成值得保留的证据。</span></div><div class="kpi"><strong>注意：不是并发评测</strong><span>本轮统一 parallel=1。结果适合比较各参数臂，不代表恢复后 parallel=2 的吞吐。</span></div></div><p class="callout">若目标是长文本，可优先保留默认 <code>--prefill auto</code>。<code>--aux-cpus auto</code> 有改善TTFT/短prompt的信号，但课本测试中decode速度和总耗时优势不大。参数选择应以实际工作负载为准；每臂只有3次正式课本样本，差异属于定性证据。</p></section>
<section><h2>官方 Strata 基准：fresh prompt 曲线</h2><p class="muted">Strata官方 <code>strata_bench.py --runs 3 --long</code>。聊天与agent各运行3轮；4K、16K、32K均为新鲜提示词，每档3次，未复用prompt。图表显示prefill中位数，旁列首字时间。</p><div class="legend">{legend}</div>{''.join(svg)}<div class="scroll"><table><thead><tr><th>配置臂</th><th>短聊decode tok/s</th><th>短聊首字 s</th><th>4K prefill / TTFT</th><th>16K prefill / TTFT</th><th>32K prefill / TTFT</th><th>Agent decode / 首字 s</th></tr></thead><tbody>{bench_rows}</tbody></table></div><p class="muted">聊天decode短请求最大输出100 token；Agent是多轮会话/缓存性能项目，不等价于Agent任务质量。TTFT越低越好，prefill/decode tok/s越高越好。</p></section>
<section><h2>课本长文本：三题正式样本</h2><p>每臂先用题1、2预热，之后固定题3、6、5为正式样本；每题约19.7K prompt token，输出上限1024。temperature 0、top-p 0.95、top-k 20、固定seed。正式请求均为fresh prompt，答案正文未写入报告。</p><div class="scroll"><table><thead><tr><th>配置臂</th><th>Decode中位数 tok/s</th><th>加权prefill tok/s</th><th>TTFT中位数 s</th><th>端到端tok/s</th><th>专家命中率中位数</th></tr></thead><tbody>{book_rows}</tbody></table></div><p class="muted">端到端tok/s按本次3个正式请求的输出token除以总体墙钟时间。模型回答有些达到1024 token上限，因此这组测试主要看吞吐与延迟，不评答案质量或完整性。</p></section>
<section><h2>本轮条件与五个独立参数臂</h2><p>所有参数臂都从相同原始配置重新开始，每次只引入各臂指定变化。共同项：parallel=1、layer-split 26、workers 15、专家缓存auto、spec 4 / min-p 0.70、pipeline-windows 2、上下文262144、KV int8 / resident32768、会话缓存16384MiB/12槽、两卡预留700MiB、<code>--mtp-hnorm stream</code>，保留BF16_TC与STAGE_TRIM；视觉关闭。为隔离参数变化，本轮关闭了batch-groups/batch-mtp。</p><div class="scroll"><table><thead><tr><th>臂</th><th>变化参数</th><th>说明</th></tr></thead><tbody>{''.join(f'<tr><td>{r["tag"]}</td><td><code>{html.escape(r["name"])}</code></td><td>{html.escape(r["note"])}</td></tr>' for r in rows)}</tbody></table></div><p class="callout warn"><b>与 EvalScope 服务配置不同。</b>本轮 benchmark 为 parallel=1、固定layer-split、关闭 batch-mtp；EvalScope 要求的生产配置是 parallel=2、layer-split auto、batch-groups=1 和 batch-mtp。两类结果不能直接横向对比。本轮已结束后恢复 EvalScope 配置，并核对配置SHA与测试前相同。</p></section>
<section><h2>与此前记录对照（仅供背景）</h2><p>历史数据是在parallel=2、auto分层、batch-groups=1/batch-mtp、显存预留550/600MiB的生产配置上测得；本轮为parallel=1、layer-split26、700/700MiB并关闭batch-mtp，因此下表不是严格A/B对照。</p><div class="scroll"><table><thead><tr><th>测试</th><th>Decode tok/s</th><th>Prefill tok/s</th><th>TTFT s</th><th>端到端 tok/s</th><th>上下文</th></tr></thead><tbody><tr><td>此前课本 hnorm stream 基线</td><td>61.3</td><td>1,248.2</td><td>15.78</td><td>31.76</td><td>约19.7K prompt，输出1024</td></tr><tr><td>此前课本 aux-cpus auto</td><td>65.5</td><td>1,277.0</td><td>15.58</td><td>32.82</td><td>同上，仅3题一次</td></tr><tr><td>本轮最佳课本decode：E aux</td><td>72.8</td><td>1,033.4</td><td>19.08</td><td>31.43</td><td>新条件，parallel=1</td></tr><tr><td>本轮最佳课本prefill/TTFT：B auto</td><td>70.0</td><td>1,169.7</td><td>16.92</td><td>32.80</td><td>新条件，parallel=1</td></tr><tr><td>旧官方parallel2基线</td><td>43.6短聊 / 56.8 Agent</td><td>803（4K）/1,251（16K）</td><td>0.75短聊 / 5.08（4K）</td><td>37.56双客户端总吞吐</td><td>旧官方基准无32K项</td></tr></tbody></table></div><p>旧课本aux与本轮E数字相近，但本轮decode较高、prefill/TTFT较低；因parallel、分层、显存预留及batch设置不同，不能把差值归因于aux参数。旧官方基线的双客户端吞吐也不应与本轮单并发数据直接比较。</p></section>
<section><h2>恢复状态与复核材料</h2><ul><li>五臂状态：<b>{html.escape(D['status'])}</b>；最后一臂结束时间：<code>{html.escape(D['finished_local'])}</code>。</li><li>自动恢复健康状态：<b>{html.escape(D['restored']['status'])}</b>。测试前后配置SHA相同：<code>{D['pre_run']['config_sha256']}</code>。</li><li>EvalScope 已按用户要求重新启动；当前模型IQ3、状态 <code>evaluating_iq3</code>、当前任务 <code>iq3-ifbench</code>。此前C-Eval 80 + MMLU-Pro 60 共140样本已完成，Campaign继续其余160个IQ3样本，之后再切到UD-IQ4_XS。</li><li>原始完整数据：[campaign.json](campaign.json)；本报告结构化摘要：[summary.json](summary.json)。</li><li>此前记录：[官方参数矩阵摘要](../official-parameter-matrix-20261014/结果摘要.md)、[4096与aux长文本记录](../prefill4096-aux-longtext-20261015/README.md)、[hnorm stream记录](../Strata-hnorm-stream测试-20261014.md)。</li></ul></section>
</main></body></html>'''
(ROOT/'Strata五组参数测试报告-20261015.html').write_text(html_doc,encoding='utf-8')
print(ROOT/'Strata五组参数测试报告-20261015.html')

