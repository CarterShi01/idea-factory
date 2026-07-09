# 架构流程全景 — 八段漏斗、每步的 prompt 与逻辑

> 状态:全景梳理(2026-07-08),基于当时 master 真实代码逐段核对。
> 定位:一张"看得懂整个系统怎么把噪音变成下注说明书"的地图。施工规格仍以
> `pipeline-v2-plan.md`(八段)+ `agent-service-plan.md`(agent 服务化)为准,本文
> 是它们的**可读版索引**,不引入新决策。

## §0 一条主线:成本梯度第一原则

整个架构的形状由**一条原则**决定(CLAUDE.md 的 FIRST PRINCIPLE):

> **每一步的"语义判断"来自 LLM 产的结构化字段;每一步的"逻辑判断"(阈值 / 排序 /
> 门 / 预算)是确定性代码在这些字段上跑。** 每条 idea 的 LLM 花费沿漏斗**单调递增**:
> 早段便宜(小模型、批量、单次抽取)撒在很多 idea 上;晚段贵(检索证据、顶模型、
> 多轮对抗)只花在少数幸存者上。便宜的钱早早过滤,昂贵的钱只花在上一段的幸存者上。

推论:`rank` / `portfolio` 两段**零新增 LLM 调用**,跑在上游已经付过费的字段上,
不是违反,是原则本身(它们是纯代码)。

```
recall → triage → generate → rank ──ideas.json──▶ enrich → diligence → portfolio
 捞信号   硬杀     成候选     粗排                 取证    开庭       出组合
 无LLM    无LLM    LLM✎       无LLM               LLM✎    LLM✎✎✎    无LLM
 (persona                                                            │
  子步✎)                                       bet_memos.json ◀──────┘  出向边界
                                               outcome 事件 ──▶ retro    入向边界+回流学习
```

每段边界落盘一个工件(统一信封 + schema_version 校验),所以任意段可单独重跑
(`idea run --only diligence`)、断点续跑(`--from enrich`)。

---

## §1 recall(捞信号)— 无 LLM

**逻辑**:8 个 channel adapter 各产 raw dict → `normalize` 归一成 `Signal`(带
`observed_on` / `money_trace` / `pain_statement`)。加源 = 加一个文件 + 在
`config/sources.json` 注册一行。

**channel**:static_external · hn_algolia(live 真代码)· brain(创始人 inbox)·
persona(模拟人群)· jobs / marketplace / reviews("钱在流动"三源,live 复用
vps_browser 机制)· vps_browser(挂已登录 Chrome 抓中文站)。

**唯一的"半 LLM"子步**:`persona` 源用 `persona_sim` prompt 从真实信号推断人群
痛点,产出打 `confidence=synthetic`,全链路更高证据门伺候(人群是合成的、可疑的)。

> **persona_sim system 关键指令**:「紧扣给定真实信号,不臆造、不过度乐观;优先有
> 付费意愿 / 有预算 / 已有付费替代方案的痛点(能赚钱);每条痛点给一句用户口吻的
> verbatim 抱怨」。输出 3-5 条 `{summary, verbatim, severity, wtp_hint}`。

**产物**:`recall.json`

---

## §2 triage(硬杀红线)— 无 LLM,零 float

**逻辑**:确定性红线,**一票否决,无部分得分**,在花任何 LLM 钱之前跑。这是"高效
说不"的第一道闸,和 diligence 里那道**打分**的 kill-gate 是两回事(这里不打分,
只 gate)。

- `triage_signals`(generate 之前):`observed_on` > **24 月** → 杀(`stale_24m`)。
  时间红线,alpha 会衰减是一回事,过 24 月直接作废是另一回事。
- `triage_candidates`(generate 之后):候选撞 `factors.has_hard_anti_fit`(创始人
  画像明确不适合的方向,单一真相源判定)→ 杀。
- 精确 + 近重去重(`runtime.textsim`)。

**产物**:`triage.json`

---

## §3 generate(成候选)— LLM✎(便宜段,batch,temp 0.9)

**逻辑**:三条路径。默认 `rule`(离线夹具零 token,CI 用);`llm` 后端时:
- **per-source 分叉**:每条信号带**来源专属 guidance**(`source_guidance` 表)。
- **跨源融合**:不同来源信号聚到同一主题(词法 Jaccard,无 embedding)→ 额外
  fusion 请求,候选打 `fusion_sources` 标签(三源融合 = 护城河信号)。
- 两批合成**一次 batch**(成本控制)。产出后立刻过 anti-fit 红线(§2)。

**generate 是整个系统最重的 prompt**,核心是一条"按来源分叉铁律":

> **⚑ 全局最高优先级·按 user 消息的 `来源` 字段分叉**:
> - **`external_event`**(实时英文 HN 等外部市场信号):**垄断铁律全部作废**。就
>   信号主题本身、面向它真实所在的市场(通常全球/英文或泛中文通用市场)产**中文**
>   idea,靠"需求热度 + 时机窗口 + 执行力"取胜,**允许无独占壁垒的通用高热度方向**
>   (这正是想要的英文侧机会)。硬禁:①把主题嫁接到蒙语/内蒙/安全云/硬件出海
>   (跑题);②target_user 换成内蒙古/蒙语人群(必须是该主题真实用户)。
> - **`pain_persona` / `brain_inbox`**(中文人群痛点 / 创始人灵感):才走**垄断铁律**
>   ——「**从『独占资源』反推痛点,不是先有通用痛点再贴标签**」(投资人 ff2 复评的
>   最关键改动)。三步顺序不许颠倒:①先列创始人独占资源(蒙语/内蒙独占进入权 >
>   安全云销售内幕 + 引荐 > 出海硬件渠道 > 医生/心理人脉;6万启动资金是**约束不是
>   资源**,必须能预售/早收钱)→ ②找只有用这个资源才能解决 / 才能卖进去的痛点
>   (痛点从资源长出来)→ ③产 idea。

> **user_template**:用 Verbalized Sampling 产 3-5 条**解决角度互不相同**的候选,
> 每条必填 `mechanism`(不许只说"AI/LLM 智能体")、`why_now`、`mvp_week1`,以及
> monopoly 三问 `why_only_me` / `first_10_customers` / `copy_fails_because`。若
> `money_trace` 非空(有人正在为此付费/雇人/成交)= 最强证据,务必写进 pain/why_now。

**产物**:`candidates.json`。体现"生成过量,质量把关是下游的事"原则。

---

## §4 rank(粗排)— 无 LLM,纯代码跑在 generate 已付费的字段上

**逻辑**:`alpha = 因子加权和 × 时间衰减 × commodity 硬罚`,再 MMR 重排 + 去聚类。

- **因子库**(`factors/`,单一真相源,各段共用,纯 `候选 → float` 词表命中):
  `pain_intensity` · `distribution_fit` · `payment_signal` · `moat_signal` ·
  `market_freshness` · `build_cost` · `competition_density`。
- **权重**(`DEFAULT_WEIGHTS`,和为 1):痛点 0.25 · **获客垄断性 0.25** · 付费信号
  0.20 · 护城河 0.12 · 新鲜度 0.10 · 可落地 0.05 · 竞争稀缺 0.03。ff2 教训:把
  `distribution_fit` 从 0.05 抬到与痛点并列,让"获客垄断性"真正决定排序。
- **时间衰减**:半衰期 30 天,地板 0.4(古老信号仍留 40% alpha)。
- **commodity 硬罚**:`distribution_fit < 0.3`(连引荐渠道都没有的通用货)→
  alpha × 0.4。软权重压不住(高的其他因子能把它抬回来),所以用乘性硬罚。
- **选择**:MMR(alpha 高 + 多样,`diversity_lambda=0.3`)+ **硬去聚类**(防"15 条
  里 4 条都是语音备忘转任务")+ 桶配额粗排(中文为主 + 英文桶硬顶)。

**产物**:`ideas.json` ← **便宜/昂贵半场的核心缝**。Studio / top3 / scripts 都读它。

---

## §5 enrich(取证)— LLM✎(常开,fixture 默认)

**逻辑**:三个 fetcher(竞品定价 / 招聘 / 成交)给每条 rank 幸存者配"钱的证据链",
过**证据门**:≥1 付费证据 + ≥1 竞品定价 + 触达路径成立(证据支撑或候选自带
`first_10_customers`)才算 `ready`。>24 月的证据抓回但 `valid=False`(不计入门,
但仍给评审看"这条已过期")。

**关键顺序**:enrich 在 pipeline 里提前到 critique/judge **之前**跑,证据才能真正
喂进后面的 prompt(`evidence_block`)——这是 M-A 之后的核心缝。证据门**不杀**候选,
缺证据的照样进 diligence,由 `enforce_evidence_grounding` 压成 REVIEW。

**产物**:`evidence.json`(items=证据;`extra.gate`=每候选门结果)

> live 真信号地基:recall 三源已接通 vps_browser 机制(`--live` 验证跑通);enrich
> 三 fetcher 的 live 是 C2+C3 合并票,卡在一个设计岔口(per-candidate 重抓 vs 复用
> recall 已抓页),见 `agent-service-plan.md` §5-①。当前默认 fixture 支撑离线。

---

## §6 diligence(开庭)— LLM✎✎✎(漏斗最贵,只看少数幸存者)

严格按顺序,五个子步:

**① gate(规则前闸,零 token)**:任一关键维度(`pain_intensity` / `build_cost`)
有致命短板即杀,不许被其他高分平均掉(idea-validation-agents 的教训)。伪痛点
击杀线(pain<0.15;synthetic<0.30)。幸存者得 0-100 rubric 分 + 最危险假设 +
**规则版实验规格保守默认**(`_EXPERIMENT_SPEC`,M-A 新增,保证 rule-only 也有完整
规格能过 enforce)。

**② critique(devil's advocate,temp 0.5)**:先于评委撕碎每条 idea。
> **critique system 关键指令**:「默认**拒投**,不评分、不写软话、绝不夸优点,只找
> 它为什么会死。五类要害往死打:①伪痛点/编造证据(揪'拿邻近购买冒充付费意愿')
> ②创始人根本做不了(founder-fit,最重要——6万烧得起获客吗/有渠道吗/号称的优势跟
> 这条对不对得上)③市场假的或太小(含'独占但盘子过小'陷阱:蒙语区 SaaS 能有几个
> 客户)④护城河=0(周末能抄)⑤时机错。至少一条必须是 founder-fit/资金渠道攻击。
> 每条反驳具体可证伪,≤40字,不许造谣。」同样按 `来源` 分叉(external_event 不拿
> "没独占/谁都能做"当致命伤,改从市场维度攻)。

**③ judge(LLM-as-judge,temp 0.1)**:只看 gate 幸存者(token-thrifty),反谄媚。
> **judge system 关键指令**:「必须在 `respond_to_critique` 里对最致命的几条逐条
> 回应(不许装没看见);五维打分 pain_real/solo_buildable/reachable/defensible/
> timing(全 0-1 必填);**反编造付费证据**(买过第二大脑课≠会为你的语音转 PRD 付费);
> **区分'触达难'与'盘子太小'**(独占但市场不存在也要点破);置信度如实,`low+pursue`
> 或 `low+kill` 会被强制降 review;**引证纪律**:引证据必须用 evidence_block 里真实
> id,编造 id 会被剥离,证据非空但 kill 一条没引用会被打回复核;**实验规格纪律
> (M-A 新增)**:pursue 必须产完整 `experiment`(metric/target/kill_below/
> horizon_days/budget_band),缺则被系统强制降级 review;长度纪律反 verbosity bias。」

**④ enforce(纯代码强制纪律,裁决后 pass)**:
- `enforce_citation`:剥离幻觉引证;有真证据但 KILL 一条没引用 → 降 REVIEW。
- `enforce_evidence_grounding`:无证据支撑的 PURSUE → 降 REVIEW(`evidence_demoted`)。
- `enforce_experiment_spec`(**M-A 新增**):PURSUE 缺完整实验规格 → 降 REVIEW
  (`experiment_demoted`)。与证据门同一纪律:不可证伪的 PURSUE 不配叫 PURSUE。
- `enforce_forced_distribution`:PURSUE 占比超 50%(弱者优先)→ 降级(高效说不)。

**⑤ persona_pressure(advisory,不改判决)**:只对最终 PURSUE 幸存者跑(量最小、
成本梯度最贵那段)。
> 「你扮演真实目标用户(不是评委不是投资人),第一人称说你为什么不买/不用——具体、
> 点名实际顾虑(价格/信任/习惯/替代/嫌麻烦),≤50字」。周报渲染"人群反对声"。

**产物**:`verdicts.json`(每条 `Evaluation` 的 to_dict + ledger 三日志)

---

## §7 portfolio(出组合)— 无 LLM,零 token

**逻辑**:`diversify`(来源桶配额中文为主 + 创始人边单边上限 + 近重去聚类)选出终端
组合排到头部 → 写产物:
- `decision_memos.md`(日常决策备忘)
- `weekly_report.md`(**北极星工件**,top-N 幸存者,每条带证据链 + **结构化实验
  规格渲染**,M-A 后从 `e.experiment` 渲染而非从证据猜定价)
- **`bet_memos.json`**(M-A 新增,出向边界工件,见 §8)
- calibrate 因子相关性摘要(样本 ≥ min_sample 时附进周报;由 `pipeline.py`
  预计算注入 `StageContext`,避免 portfolio 直接 import 兄弟段 retro 违反分层铁律)

+ versioning 快照本次 run 的全部工件(每个历史 run 完整可回放)。

---

## §8 两个边界工件 + retro 回流学习

投研部与 oc 之间**只交换两种工件**(`agent-service-plan.md` §2)。

**出向:`bet_memos.json`**(M-A)—— 机读的"下注说明书":
```
{bet_id, run_id, title, verdict,
 hypothesis{pain, solution, target_user, why_now, why_only_me},
 evidence[…引证过的证据链…], riskiest_assumption, killer_objection,
 persona_objections[…], experiment{metric,target,kill_below,horizon_days,budget_band},
 eval_score, confidence, lineage_url}
```
`GET /api/bets`(bearer 鉴权)供 oc 消费。**核心契约:`experiment` 与
`Outcome.prediction` 同构**——下注时写的赔率 = 复盘时对账的口径,`prediction_error`
直接可算,闭环锁在 schema 层不靠纪律。

**入向:`POST /api/outcome`**(M-B)—— oc push 赌局结果:
```
{event_id(幂等键), candidate_id, tested_at, metric, actual,
 target?(缺省从 bet memo 补), first_revenue?, lesson?, reported_by}
```
**采集是 oc 的(push),消化是 idea-factory 的(被动收→ledger→retro/calibrate)**。
idea-factory 永不主动读 oc 看板。`idea retro` CLI 是同一收件口的人工版。

**retro(回流学习,CLI 侧第 8 段)**:
- `record_outcome` → `outcomes.jsonl`。
- `retro_lesson` LLM(可选,创始人手打 lesson 优先零 token):
  > 「预测 vs 实际 + 当初裁决上下文 → 一句可复用教训,≤50字,不许'继续加油'空话」。
- `calibrate`(**只读,永不写配置**):样本 ≥ 10(带 target 且能查到 factors 的
  outcome)才给每个因子与"1+预测误差"的 Pearson 相关性,人工决定要不要调权重;
  样本不足**明确返回"不足"**,不静默假装算出来。

---

## §9 横切:可解释(已是强项,本轮未动)

- **`/api/ask`**:就一条 idea 自由追问,从血统工件拼上下文。
  > 「**只依据上下文回答,不编上下文没有的证据/数字**;没有就直说'当前数据里看不到';
  > 被问'为什么被 pass/为什么这个裁决'时直接指向具体字段与阈值(证据门缺哪项/哪个
  > 因子分低/哪条 killer_objection)」。每轮落 trace(stage=ask)。
- **全链路 trace**:每次 LLM 调用的 prompt+response+usage+cost+latency 落
  `data/ledger/traces/<run_id>/<stage>.jsonl`——成本梯度一眼可见(便宜段每条百
  token、昂贵段每条数千,沿漏斗单调递增)。
- **Studio v2**:运行为轴的调试台(RunFunnel → StageDrill → IdeaLineage),
  hash 深链可书签。

---

## §10 一张表:每段"LLM 产字段 vs 代码判断"

| 段 | LLM 后端 | LLM 产什么结构化字段 | 代码用这些字段做什么确定性判断 |
|---|---|---|---|
| recall | persona_sim(仅 persona 源) | 人群痛点 {summary,verbatim,severity,wtp} | normalize 归一,synthetic 标记 |
| triage | 无 | — | 24月红线 + anti-fit 红线 + 去重(一票否决) |
| generate | ✎ 便宜段 | mechanism/why_now/mvp/monopoly三问/prob | anti-fit 红线杀 |
| rank | 无 | (用 generate 已付费字段) | 因子加权 × 衰减 × commodity硬罚 + MMR + 去聚类 |
| enrich | ✎(future evidence) | 证据结构化(fixture 默认) | 证据门三条件 + 24月失效 |
| diligence | ✎✎✎ 最贵段 | 五维分/critique/rebuttal/experiment/reasons | gate击杀 + 4道enforce强制纪律 + 强制分布 |
| portfolio | 无 | (用 diligence 已付费字段) | diversify 配额 + 出三报告 + bet_memos |
| retro | retro_lesson(可选) | 一句 lesson | calibrate Pearson(样本门,只读) |

**Dify 镜像不变式**:只有 `generate` / `critique` / `judge` 三步的 prompt 正文锁在
`dify/flows/*.yml`,`config/llm/*.json` 是镜像,两处必须逐字一致(CI 钉死:
`test_dify_mirror_invariant`)。persona_sim / persona_pressure / ask / retro_lesson
不在 Dify 上,只有 `config/llm/*.json` 一处。

**LLM 后端**:默认全关(离线零 token,`idea run` 裸调用是项目身份);opt-in 切
腾讯 router(LKEAP tc-code/tc-think,1亿token=100元)走 `scripts/weekly-run.sh`。
CC-handoff 仅人工跑批(`--*-backend cc` → `/run-llm-batch`),从不自动调 CC。
