# Strata / Hermes 夜间调优执行方案

版本：2026-10-20。状态：方案已准备，尚未开始测试，尚未修改服务或功耗。

本文件供后续执行会话直接使用。用户发出开始指令后执行；它本身不是定时任务。默认总预算为启动后 8 小时。所有百分比门槛都是本次实验的预设决策规则，不是厂商保证或统计显著性的替代品。

## 1. 目标与已确认的入口

目标：固定 Huihui 模型，以工具任务正确率不下降为前提，降低真实 Agent 完成任务的时间。独立记录冷 prefill、缓存续轮、decode 和功耗，避免将不同负载的 tok/s 混成一个总分。

| 项目 | 2026-10-20 只读核验结果 |
|---|---|
| Strata | GPUServer-1，10.2.21.4；0.1.45；源码 477ac13cbe8e582c20484871ce459d20d82df09d |
| 模型 | huihui-qwen3.8-flash-next-abliterated-ud-iq4_xs，外置 Q8 PLE |
| 推理 GPU | 两张 RTX 2080 Ti 22GB；当前各 180 W，设备报告默认各 250 W、最大 280 W |
| 视觉 GPU | RTX 2070 SUPER，当前与默认均 215 W |
| 限功耗服务 | /etc/systemd/system/nvidia-power-limit.service；enabled、active(exited)，oneshot，无 ExecStop |
| Strata 配置 | /opt/strata-data/config/strata-huihui-ud-iq4_xs-q8ple-vision-v0.1.45.json |
| Compose | /opt/strata-deploy/compose.yaml |
| API | http://10.2.21.4:8080/v1；核验时 health=ok、loaded=true、无 API key |
| Hermes | 10.2.21.6，主机名 Hermes-1，Linux 用户 hermes，UID 1001 |
| Hermes 版本 | v0.22.1+163.g046094d，commit 046094df28b712f62a5e3c728a9e59da05dcbf1e；源码工作树干净 |
| Hermes CLI | /home/hermes/.local/bin/hermes；已确认支持 --oneshot、--query-file、--format stream-json、--resume、--max-turns、--run-budget、--reasoning、--provider、--base-url |
| Hermes 容器 | rootless Docker 活跃；unix:///run/user/1001/docker.sock；现有 nousresearch/hermes-sandbox:desktop 镜像 |
| Hermes → Strata | 从 10.2.21.6 请求 Strata /health 返回 HTTP 200 |

SSH：Strata 使用当前工作目录 work/id_ed25519_pve_local 和 work/known_hosts_vm502；Hermes 使用 C:/Users/someo/.ssh/id_ed25519_frontend 及现有 known_hosts。仅引用密钥路径，不将密钥内容写入报告。

正式开始时重新读取上述状态；不要升级 Hermes、Strata、驱动或模型。若版本/模型已变，建立新的基线，不能直接复用本文件中的历史成绩。

## 2. 基线及不可变项

保留三种身份：

1. S0：开始测试时的线上配置，完整备份，用于紧急回滚。
2. B0：抄作者参数之前的原始配置，在 250 W 下重新测。来源：outputs/author-profile-20261019/original-config.json。
3. I：当前胜出候选。每个阶段只从 I 派生少量候选，只有通过门槛才替换 I。

B0 的主要值：prefill auto:8192，spec=4，spec-min-p=0.50，workers=15，pipeline-windows=2，mtp-hnorm=stream，KV int8，kv-resident=32768，max-context=262144，显存预留 700/700 MiB，layer-split=auto，会话缓存关闭；BF16_TC、STAGE_TRIM、SM75_PERF、PA_V2T 开启。未指定的值以完整配置和实际 INFO 为准。

S0 核验时为 500/600 MiB 预留、spec-min-p=0.70、SELECT_SIMT=2、REFILL_PARTS=1、PREFILL_HELP=1、会话缓存关闭。可以将 S0@250W 作为一个整体候选与 B0 比较，不能把它的差异归因于其中某一个开关。

整晚固定：模型与 PLE 文件、引擎二进制、worker 数、VM CPU/NUMA、显卡顺序、KV 类型、上下文上限、客户端工具定义、工具输出上限与重试策略。GPU 参数筛选阶段固定 250 W。不扩展到新模型、CPU、NUMA、磁盘或视觉优化。

每次启动保存完整 args/env 和配置 SHA256，并从 /metrics、启动日志核验实际值、分层点、专家缓存 MiB/slots、MTP 位置、prefill_pipe。变量未实际生效，标记 NOT_APPLIED，不能当作零收益样本。

## 3. 第一步：恢复默认功耗

开始执行后，先保存 service 内容、启用/活动状态和三张卡的 UUID、限制、默认限制。然后在 GPUServer-1 执行：

```bash
systemctl disable --now nvidia-power-limit.service
nvidia-smi -i GPU-be897daa-b730-b812-cac5-0677e7c00d5b -pl 250
nvidia-smi -i GPU-9a371e9d-99d5-eb30-e2f1-1a8cef3b6f03 -pl 250
nvidia-smi --query-gpu=uuid,name,power.limit,power.default_limit --format=csv
```

执行前必须核对两个 UUID 仍对应两张 2080 Ti。仅停止 oneshot 服务不会撤销已设定的 180 W；显式设置并读取验证不可省略。恢复到默认 250 W，不使用最大 280 W，也不改 2070 SUPER。

所有参数筛选都在 250 W 下进行。最后再用胜出引擎参数对照 250/180 W；有时间加 220 W。这样功耗不会混入每次参数比较。

## 4. Hermes 测试环境与记录方式

使用现有 Hermes 代码和 CLI，但创建专用 HERMES_HOME：/home/hermes/strata-bench/<run-id>/homes/<case-run>。工作区为该 run 下的 workspaces/<case-run>。不修改日常 Hermes profile，不启动或改动日常 Gateway/Studio，不复制生产 .env、记忆、MCP、hooks 或外部服务凭据。

测试配置显式指定 custom provider、目标模型与 Strata 地址，禁止 fallback 到其他模型。只启用 terminal,file。CLI 必须以 hermes 用户运行。终端和文件工具进入专用 rootless 容器，只挂载当前题目的工作区；不挂生产目录、Docker socket 或 SSH 密钥。容器使用已存在镜像并记录 image ID；工具容器网络关闭，模型 API 请求由 Hermes 宿主进程发出。

采用最小测试 config.yaml，显式固定工具截断、压缩和记忆策略。先读取实际版本的配置实现，确认字段名称；不能用 --safe-mode/--ignore-user-config 意外绕过自己配置的 Docker 后端。可以用 --ignore-rules 隔离日常规则。API 使用无权限的占位 key 仅满足 custom provider 形状要求，不使用真实云端 key。

若需要逐请求计时，在 Hermes 宿主启动仅监听 127.0.0.1 的记录代理，转发到 Strata；代理不切换模型、不自动重试，不篡改消息和工具 schema。允许统一附加已验证受支持的测试采样字段。每次请求记录请求 ID、规范化请求哈希、单调时钟耗时、reasoning/text/tool-call 流事件、用量及完成原因。禁止把 API 凭据写入日志。

CLI 调用形状（执行时由 Python subprocess 参数数组构造，不用字符串拼 shell）：

```text
hermes chat --oneshot --query-file <prompt.txt>
  --model huihui-qwen3.8-flash-next-abliterated-ud-iq4_xs
  --provider custom --base-url http://127.0.0.1:<记录代理端口>/v1
  --toolsets terminal,file --reasoning medium --ignore-rules
  --format stream-json --max-turns 12 --run-budget 300
```

接入验收：结构化轨迹出现真实工具调用；Strata 侧请求数与代理一致；实际 model 正确；无外部 fallback；文件读写实际发生在专用容器；会话保存和按 session ID 恢复成功。--help 成功不等于以上接入已验收。

测试采样冻结为 medium reasoning、temperature=1.0、top_p=0.95、top_k=20（该模型支持时）、max_tokens=4096；配对 seed 一致，前提是请求/服务实际支持。请求抓取不到这些有效值就先修复 harness，不能静默退回 none 或另一套采样。固定 seed 不保证不同内核/配置输出逐字一致，记录实际输出和 token 数。

每个 Agent case 的总墙钟上限 300 秒，全部用户轮次合计最多 12 次工具迭代；外层控制器给 30 秒清理余量。达到限额记失败，不偷偷提高预算。出现交互审批、未知外部依赖、网络请求或凭据请求时，记录 BLOCKED 并结束该 case，不整晚等待，也不扩大权限。只允许对已知基准用到的工具命令设窄范围非交互策略。

## 5. 自动判分的 Agent 题库

执行准备阶段生成 6 类 × 2 个固定数据种子，共 12 个 case。第一轮使用种子 20261020、20261021；后续配置使用同一份冻结题库。每个 case 是同一个 Hermes 会话中的一个或多个用户轮次，不以“回答说做完了”判定通过。

| 类型 | 提交给 Hermes 的任务 | 可信判分器的验收 |
|---|---|---|
| T1 数据清洗与汇总 | 读取含重复交易版本、取消单、退款的 CSV，按明确规则输出 result.json；金额采用整数分 | 独立 oracle 精确比较所有分组、数量和净额；输入哈希不变 |
| T2 SQLite 查询 | 从只读样例库关联客户、订单、支付，按指定日期边界计算排名，输出 result.json | 在基准生成时用可信 SQL 计算答案；行集合、排序、金额完全相符；源数据库不变 |
| T3 修复 Python 函数 | 修复小模块的区间合并/边界处理；提供契约和少量公开例子 | 在全新无网络验证容器中运行约 20 个隐藏用例；空输入、乱序、接触边界、嵌套区间等全部通过；只允许修改指定源码 |
| T4 配置迁移 | 把旧版 JSON 服务配置迁移为新版 JSON，保留未知字段，规范化端口并排序去重 | 精确比较解析后的对象；原文件不变；不能靠 JSON 字符串顺序误判 |
| T5 合成日志取证 | 在 4 份相关日志中找出指定请求的首个失败组件和传播链，输出规定 JSON | 注入故障时同时生成 oracle；request_id、组件、错误码、时间和因果边完全匹配；不依赖人工解释 |
| T6 多轮状态任务 | 在三轮用户要求中创建库存表、应用一批变更、再修正其中一项并输出最终状态 | 每轮输出和最终台账逐项精确比较；session ID 保持；续轮保留真实 assistant/tool 消息；不能新开对话冒充连续任务 |

代码、数据和最终输出全部限于题目目录。不同 case/配置使用干净工作区和独立 Hermes home；T6 内的用户轮次共享同一 home/session。测试前生成 manifest（文件 SHA256、明确任务契约、允许修改的路径、oracle、运行限额）。隐藏答案和判分器由控制器持有，不挂进被测 Agent 容器。

判分器必须先自测：可信正确结果通过；至少三类错误结果（缺字段、错数值/边界、篡改输入/验证器）失败。代码题故意有 bug 的初始实现必须失败，可信修正必须通过。不得为提高通过率修改已冻结的答案、题目、阈值；确属 harness 错误时提升套件版本，并对所有配置重跑受影响题目。

初始 B0 至少通过 11/12 才将此题库用于自动调优晋级。低于该值，转为工具兼容/模型能力诊断，保留所有失败轨迹，停止参数晋级；不要不断降低题目要求。已有失败也必须在最终报告保留。

BFCL 全量、联网搜索、开放式写作、审美性代码评审留到以后。这 12 题是内部工程验收集，不宣称代表完整 BFCL 或普遍 Agent 能力。

## 6. 引擎性能与缓存协议

两套协议分开标注：

- E（冷引擎微测）：固定正文的 2K/约10K/32K，简单代码/工具 JSON 各选代表题，输出上限 512；temperature=0、reasoning=none，用于低成本筛选与历史口径延续。每个配对使用同一正文和同一标记；不同配对可用冻结的不同标记，禁止实时 timestamp 改变 A/B 输入。每次确认 reused=0。
- A（实际 Agent）：第 5 节真实 Hermes 工具循环，使用固定 medium reasoning 与实际采样。E 赢不等于 A 赢，最终晋级必须看 A。MTP 阈值和窗口初筛还必须加入至少一个使用 A 采样设置的代码/工具输出请求，不能只靠 greedy 计数题决定。

E 正式测量前固定执行两项预热，4K/32K，各生成 128 token；预热不计分。每个 arm 都执行相同预热。记录温度、时钟和实际专家容量；不要求把专家缓存逐槽锁死，但必须保留其状态差异。

缓存协议 C：分别建立 32K 和 128K 的受控历史，再追加 0.5K、2K、8K 工具结果；另做 A→B→A→B 的会话交替。必须通过 API 实际加载历史，不能仅把长文件放到工作目录就宣称有 128K 上下文。多轮保留真实输出与 tool-call IDs。已知简单事实问答采用 JSON exact match；重复使用可读的静态历史，不能在请求开头加入变化的时间/会话标识。

C 比较 conversation-cache=0 与 8192 MiB / 4 slots。活动会话 prompt-cache 均保留默认，不将“会话缓存关闭”误写成“全部前缀缓存关闭”。记录 parked/restored/evicted、实际复用 token、重新读取 token、每轮 TTFT 和整串耗时。128K 返回会话中复用目标为共有前缀的至少 80%；32K 考虑 16K 检查点间隔，仅报告实际比例，不机械套 90% 门槛。长会话无法命中时先诊断前缀序列化与容量，不得据此宣布缓存无收益。

每个请求同时记录：完整 prompt tokens、新读取/复用 tokens、prefill 毫秒、引擎 decode tok/s、全部输出 tokens（含 reasoning）、首个流事件、首个可见文本、完整工具调用可执行时刻、请求结束时刻。以完整工具调用时间衡量工具轮次，不把 TTFT 当成开始执行工具的时刻。

每张 GPU 独立每秒记录功率、温度、核心/显存时钟、利用率、功耗/热限频原因、PCIe RX/TX；保留同步时间戳。能量通过功率积分计算，只称 GPU 能量，不冒充整机墙上电量。每轮记录主机可用内存、swap-in/out、boot ID、日志游标。

## 7. 夜间阶段、候选及预算

绝对上限是开始后 8 小时；第 4 小时之后不再探索新参数，至少为最后验收与恢复留 2 小时。每阶段超出预算即保留 incumbent 并继续下一阶段，不以用户未回复为批准去扩大实验。以下是预算，不是保证完成时间。

| 阶段 | 操作 | 预算上限 | 自动处理 |
|---|---|---:|---|
| P0 | 备份、恢复 250W、临时 Hermes home/容器、生成/自测题库和日志代理 | 45 分钟 | 接入失败可继续 E 微测，Agent 与最终晋级标记未完成 |
| P1 | B0 同配置重复；12题初始基线；S0@250W 小规模对照 | 75 分钟 | 基线质量不足停止晋级；同配置噪声过大不继续排名 |
| P2 | C 缓存协议，0 vs 8192/4 | 30 分钟 | 真实续轮收益达门槛才保留缓存；否则保持当前 I 的缓存值 |
| P3 | MTP布局 L0/L1/L2 | 35 分钟 | 三组选一；不生效的组跳过 |
| P4 | prefill-pipe 0/1/1536/6144 粗筛 | 35 分钟 | 有明显方向才补 768/3072；否则默认0 |
| P5 | spec-min-p 0.30/0.50/0.70；有时间再 spec 2/3/4 | 40 分钟 | 达第4小时立即结束探索；hnorm pooled 留到有余量再测 |
| P6 | 最终 I 与 B0 的 12题配对验收、长上下文回归、关键题复测 | 120 分钟 | 不满足全部晋级条件就不宣布胜出 |
| P7 | 在最终选定引擎配置上对照250/180W，有时间加220W | 25 分钟 | 仅决定功耗建议；正常收尾恢复250W |
| P8 | 恢复确定配置、健康/工具烟测、整理结果 | 15 分钟 | 最迟总预算结束前开始 |

阶段预算累计可能接近上限；以全局时间门槛为准。P0/P1 过长时，P4/P5 首先缩减，不挤掉 P6/P8。同一时间只运行一个 benchmark 负载；其他业务请求进入 Strata 时标记该配对污染，最多重跑一次，不停止其他业务来凑成绩。

L0：pipeline-windows=2、MTP在后卡、SPLIT_MTP_BATCH=0。

L1：在 L0 基础上只开 STRATA_SPLIT_MTP_BATCH=1。必须出现实际 batched K/V 日志；prefill与decode同时比较。

L2：在 L0 基础上只开 STRATA_MTP_STAGE0=1，SPLIT_MTP_BATCH=0。必须确认草稿位置真的改变；记录专家缓存分配变化。

0.1.45 的 split batched K/V 条件含 !mtp_first，所以 L1 与 L2 不能当作可叠加优化。若相关文件/模式不支持，不自动迁移 MTP、换模型或改源码，记录原因并跳过。

prefill-pipe R 不是 chunk token 数。测试时保持 auto:8192 上限与胜出布局，读取实际 chunk。先测0/1/1536/6144，有收益再局部细化，不做整个参数空间的笛卡尔积。

MTP 顺序：先布局，再阈值，再窗口。阈值与窗口的候选去重，已在 incumbent 中的值不用另启动同义配置。记录 drafts_offered/accepted、tokens/window、draft/verify耗时、pipeline回退。需要归因时只给有代表性的请求启用 STRATA_DECODE_TIMING/STRATA_VERIFY_PROFILE；正式速度数据不带 profiler。不以接受率最高直接判胜。

## 8. 重复、排名与验收标准

### 8.1 基线稳定性

B0 在两次独立引擎启动后，各对相同代表题跑3次。每题的 max/min 应不超过1.10，两次启动中位数差应不超过5%。超标可统一延长预热并完整重做一次。再次超标则标记 BASELINE_UNSTABLE，停止微小参数收益排名；仍可完成缓存可用性与工具正确性检查。不能删除慢样本来满足门槛。

### 8.2 参数初筛

每个新候选先运行一遍小套件。全部失败/不生效者不再测；速度落后超过10%且无另一项明确收益者淘汰。其余候选相对当前 I 做至少3个配对，顺序平衡为 I-C / C-I / I-C。每个 arm 以独立启动或已确认可无状态切换的方式设置，预热一致。初筛结果只能叫候选，不能直接上线。

对相同 case 的中位延迟取比值，并用等权几何平均汇总；不要将不同长度的 tok/s 直接取平均。候选初步晋级要求：目标延迟至少降低8%，3个配对至少2个同方向，另一关键指标不退化超过5%。缓存阶段用续轮/切换延迟作目标；MTP阶段用单位实际生成token时间及小型Agent任务延迟；prefill阶段用首工具就绪/TTFT，另保留decode守门。

没有达到门槛就保留 I，并记录差异处于未确认范围。一个阶段不胜出不阻止其后阶段；最终配置未必是全局最优，报告必须说明这是限时逐阶段筛选。

### 8.3 最终 Agent 验收

I 与 B0 使用相同的12题、固定种子、工具与采样条件，平衡运行次序。每题从干净容器/工作区开始；T6 内续轮不清状态。两个配置至少各跨2次引擎启动，避免把一次幸运启动当结论。

必须同时满足：

1. 候选通过数不低于 B0，至少11/12；B0通过的题不能出现已确认的新失败。
2. 任一新失败或基线失败，在两种配置下均补测同一题2次。候选独有失败在总3次中出现至少2次，判质量退化，淘汰。偶发或双方不稳定，标记需复核，不能全自动晋级。
3. 共同成功题的配对总任务耗时几何平均降低至少8%，且至少8/12题不更慢。固定选4个代表题（T1、T3、T5、T6各一变体）追加配对复测；改善须在两次启动均同方向。
4. 所有题总耗时（每个失败按300秒计）不能变差；至少11/12个任务完成。不要只比较成功子集而隐藏失败成本。
5. 128K冷输入TTFT及长历史续轮延迟分别不退化超过10%。240K仅做上下文/OOM回归；它不决定默认配置的排序。
6. 无新增运行错误、硬件异常、验证器篡改、输入破坏或非测试目录写入；无模型回退或意外联网服务调用。

12题只是内部回归证据，不代表统计学证明了普遍质量等价。若8%改善门槛未达，输出“未找到足够明确的胜出配置”，保留 B0，而不是选一个表中看起来最高的数。

### 8.4 缓存与内存验收

缓存实际 park/restore 生效；128K会话返回时共有前缀复用≥80%；续轮/交替序列中位耗时降低≥15%；冷输入TTFT退化≤5%。执行期间 MemAvailable 保持≥8 GiB，连续10秒swap-in超过1 MiB/s视为内存压力，缓存候选淘汰。若8 GiB缓存容不下测试会话，只允许加测16 GiB一次且满足相同余量条件，否则报告容量不足，不自动扩展VM。

### 8.5 功耗对照

固定最终引擎配置与测试内容，250/180W各至少3次配对，使用32K复杂输入和一个实际Agent代表题。若有时间增加220W。记录整请求时间、GPU能量、温度、限频原因；不能用“设置了250W”当作实际消耗250W。

低功耗档如完成时间退化≤3%且GPU能量降低≥10%，可列为节能推荐；本轮正常收尾仍按用户恢复默认功耗的目标保留250W，等待用户决定是否长期采用低功耗档。

## 9. 错误分类与自动收尾

| 事件 | 自动处理 |
|---|---|
| 单题逻辑错误、工具JSON无效、超时 | 保留轨迹，记失败，继续下一题；按最终验收规则补测 |
| 候选启动失败/显存OOM | 该候选淘汰，恢复I；最多一次恢复启动；不自动削减上下文/模型 |
| 同一候选两次服务崩溃 | 淘汰候选，停止该分支；恢复最后健康配置 |
| 新fatal MCE/ProcessorError、boot ID变化、GPU Xid或设备丢失 | 结束整晚负载，采集日志；主机可达时恢复S0和原180W服务；不自动重启宿主/重置GPU反复试 |
| GPU达到90°C，或≥85°C持续30秒 | 终止当前负载、降回180W、记录热问题，停止高功耗分支；这是本次保守运行阈值，不是厂商极限 |
| 原有NVMe corrected AER | 记新增计数，不单独判CPU/引擎失败；出现uncorrected错误另行停止并记录 |
| 任务出现人工审批/未知依赖 | 结束该题并记BLOCKED，继续独立测试，不请求放宽权限 |
| 外部请求/后台负载污染 | 标记并最多重测一次，不能无限重跑 |
| 到达截止时间 | 保存已完成结果、恢复已确认配置并健康核验，未测项列为未完成 |

日志检查以开始时boot ID、journal cursor为基准；旧BERT记录在本次启动一直存在，不等于测试过程中又发生一次fatal。

正常结束：有完整胜出配置就应用胜出配置，否则使用B0；保持两张2080Ti默认250W且原180W服务disabled。执行一个真实工具烟测、一个缓存续轮（如果开启）、读取health、实际参数与功耗。若这些收尾核验失败，恢复S0与开始前服务/功耗状态，标记回滚；不得报告部署成功。

如果硬件异常导致机器不可达，记录“无法完成回滚”，不声称已恢复。Agent进程、代理、容器仅清理本run创建且登记的资源；保留所有结果和失败样本。

## 10. 必交付文件与留到白天的问题

每个arm输出：effective-config.json、request-metrics.jsonl、gpu.csv、health-events.jsonl、Hermes轨迹、判分结果、日志摘要。全局输出：manifest.json、pairwise.csv、acceptance.json、final-config.json、回滚清单、简明Markdown/HTML报告。

acceptance.json 至少含：status（PASS/NO_CLEAR_WIN/BASELINE_UNSTABLE/PARTIAL/HARDWARE_STOP）、基线/候选哈希、通过题数、新失败、各延迟比值、配对次数、功耗、回归检查、最终实际状态和未执行项。总体性能提升以同晚重新测的B0@250W为基准，不能与旧180W成绩直接相除冒充参数收益。

白天只讨论：失败样本的语义质量、完整BFCL/开放任务是否必要、250W的性能是否值得额外电耗、未完成的hnorm/窗口细调、是否把测试配置用于长期服务。今晚不等待这些意见，也不替用户判定开放式回答是否“更聪明”。

## 来源与准备边界

- 本轮SSH只读核验：10.2.21.4 的 systemd unit / nvidia-smi；10.2.21.6 的 CLI help、git HEAD、rootless Docker 与API连通。
- Hermes CLI官方参考：https://hermes-agent.nousresearch.com/docs/reference/cli-commands
- NVIDIA nvidia-smi：https://docs.nvidia.com/deploy/nvidia-smi/index.html
- Strata 0.1.45多卡文档：https://github.com/Niko1221/Strata/blob/v0.1.45/docs/MULTI_GPU.md
- Strata 0.1.45实现：https://github.com/Niko1221/Strata/blob/v0.1.45/src/program/generate.cpp

这次完成的是运行条件核验与执行规范。临时Hermes配置、12题数据/判分器、记录代理和自动执行器尚未创建或运行；P0明确包含这些准备与自测。后续执行模型不能把此文件的存在当成测试基础设施已经验收，也不能凭CLI help就宣布Agent接入成功。
