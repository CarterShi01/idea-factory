---
doc: design
title: "Idea 漏斗:召回 → 粗排 → 精排 → 打散(借搜索推荐系统的分层架构)"
date: 2026-07-04
status: approved (2026-07-04, 创始人拍板:中文为主 ~14中/6英、英文桶 founder_fit 次要参与、切分 200/50/25/20)
related: [dify-integration.md, ../../src/idea_gen/ranks.py, ../../src/idea_core/factors.py, ../../config/founder.json]
---

# Idea 漏斗设计

> 目标(创始人):把系统从"生成一堆 → 一把排序 → 砍到 20"改成一套**分层漏斗**,
> 像搜索推荐系统那样 **召回 → 粗排 → 精排 → 打散**;每层的排序都**综合个人画像**,
> 最终选出"最适合这位创始人做"的 20 篇上 UI。20 是**终端展示数**,不是取前 20 那么简单。

## 0. 为什么要分层(现状的问题)

现状(见 `idea_gen/pipeline.py` + `idea_eval/pipeline.py`)其实已是漏斗雏形,但三个毛病:

1. **贵操作跑在全量上**:gen 把**全部** ~200 候选写进 `ideas.json`,eval 的 LLM
   critique+judge 对**全量 rule-gate 幸存者**逐条跑——精排(最贵)没有先被粗排砍量。
   token 浪费、也慢。
2. **个人画像只是"降级旗",没成为排序主力的一等信号**:founder-fit 散在
   `distribution_fit` 因子(0.25 权重)+ `moat` 的语言区域加成 + eval 的 ff1 降级旗,
   没有一个**贯穿各层的 founder_fit 分**。
3. **打散只在文末摘要做,且只按词面**:`select_diverse_top_n` 是词面 Jaccard 去重,
   没有按**来源/创始人边/人群**这些有意义的轴做组合多样性 → 终端 20 篇可能全是
   "蒙语政企工具"(刚踩过的坑),或"中英混合"失衡。

## 1. 四层漏斗(映射到现有两半架构)

**关键:漏斗天然贴合现有 `idea_gen`(alpha 侧)/ `idea_eval`(gate 侧)的隔离切分。**
两半仍只经 `ideas.json` 通信 —— 这个文件从"全量转储"升级为"粗排产出(粗排后的候选池)"。

| 层 | 住哪 | 输入→输出量(可配) | 成本 | 个人画像的角色 |
|---|---|---|---|---|
| **召回 Recall** | idea_gen: collect+generate | 3 源 × 角度 → **~200** | 中(LLM 生成) | **不介入**(召回只求覆盖广、别提前坍缩多样性) |
| **粗排 Coarse** | idea_gen: score+cut | 200 → **~50** | 低(纯因子,零 token) | **cheap `founder_fit` 因子**进 alpha(渠道独占/语言区域/anti-fit) |
| **精排 Fine** | idea_eval: gate+critique+judge | 50 → **~25** | 高(LLM 对抗评审) | **judge 深评** founder-monopoly(why_only_me 三问) |
| **打散 Diversify** | idea_eval: 组合选择 | 25 → **20** | 低 | **按创始人边/来源均衡**,组合成一个组合而非单一主题 |

切分量 `RECALL_N / COARSE_K / FINE_K / UI_N`(默认 200/50/25/20)全部走 config,可调。

### 1.1 召回 Recall(idea_gen,不变+略增产)
- 3 源 × 生成角度过量产出(Verbalized Sampling 已在做)。目标是**覆盖**,不是精度。
- 唯一过滤:dedup(精确+近重)+ 明显无痛点的丢弃。**不在这里用 founder-fit 筛**
  —— 否则重蹈"回音室"(只留像创始人的 → 多样性坍缩)。
- 源级预算(如英文 HN 按 `points` 热度截断)是**召回配额**,属本层(已实现 `_cap_english_by_heat`)。

### 1.2 粗排 Coarse(idea_gen,纯因子,零 token)
- 用因子库算 alpha(`ranks.score`)—— 便宜、确定、可跑全量 200。
- **新增 `founder_fit` 复合因子**(见 §2),与 `pain_intensity`/`payment_signal` 并列进 alpha。
- **按来源分桶粗排**(呼应"中英混合"):
  - `external_event`(英文 HN 市场机会):alpha 主由**热度×需求证据**(market_freshness +
    payment_signal + HN points),founder_fit 作**次要加权**(适合他的市场机会靠前,但不因
    "非独占"被压死 —— 英文侧本就允许通用高热度)。
  - `pain_persona`/`brain_inbox`(中文人群/灵感):alpha 主由 **founder_fit × 痛点**
    (找"只有他能赢"且痛的),这正是"综合个人画像找适合我的项目"。
- 每桶各取 coarse-top,合并成 ~50 的粗排池 → 写 `ideas.json`。**贵的 LLM 只碰这 50。**

### 1.3 精排 Fine(idea_eval,LLM 对抗)
- rule kill-gate(乘法下限,便宜)先在 50 上跑,砍掉致命硬伤(无痛点/一人做不了)。
- LLM critique(毒舌)+ judge(裁决)只对 gate 幸存者跑(已按来源分叉:英文按市场审、
  中文按独占审,见三条 Dify 流)。judge 产出 `eval_score` + verdict + founder-fit 深评。
- 精排分 = f(`eval_score`, 粗排 alpha, founder_fit 深评)。取 fine-top ~25。

### 1.4 打散 Diversify(idea_eval,组合选择)
- 在 25 上做**多轴**组合选择,产终端 20:
  - **词面去聚类**(已有 `select_diverse_top_n`,防近重刷屏)。
  - **来源均衡**:给英文机会 / 中文独占各留配额(如 UI 20 = 英文≤8 + 中文≥10 + 灵感缓冲),
    防"一次偏蒙语/一次偏英文"两个极端 —— 这是本轮反复踩的坑的根治。
  - **创始人边均衡**:蒙语/安全云/硬件出海/英文市场… 单一边设上限,让 20 篇是个**组合**。
- 输出终端 20 → `screened.json`(WebUI + `/api/top3` 读它)。

## 2. `founder_fit` 复合因子(个人画像成为一等排序信号)

新增一个纯函数因子 `founder_fit(candidate) -> [0,1]`(仍守 `candidate->float` 契约,
读 `config/founder.json`,import 时把画像折进词表,与现有 `distribution_fit` 同法保持纯)。
它综合(权重可调):

- **渠道独占**(复用 `distribution_fit` 三档:蒙语区域/家人 monopoly、B2B 引荐 referral、公开 open);
- **语言/区域护城河**(复用 `moat_signal` 的 `_MOAT_LANG_REGION`);
- **技能/资本可行性**(6 万预算 + 一人两周~两月:命中 anti-fit(重资产/大团队/长周期/牌照)→ 扣分);
- **人脉杠杆**(安全云/医生/心理教授/海外硬件 → 加分);
- **anti-fit 硬扣**(纯投放冷启动 to-C、需团队/融资续命 → 压到低分)。

粗排:`founder_fit` 进 alpha(中文桶权重高、英文桶权重低)。
精排:judge 的 why_only_me/copy_fails_because 深评作 founder_fit 的高保真复核。
这样"个人画像"从一个降级旗,升为**贯穿粗排+精排**的排序轴。

## 3. 落地映射(改动清单,尽量小、贴现有码)

- `idea_core/factors.py`:加 `founder_fit` 因子 + 注册进 `FACTORS`(契约新增、向后兼容)。
- `idea_gen/ranks.py`:`score` 支持**按来源分桶**的权重集;新增 `coarse_select(scored, k, per_source_budget)`。
- `idea_gen/pipeline.py`:score→coarse_select(~50)→写 `ideas.json`(不再全量转储);digest 仍走摘要。
- `idea_eval/pipeline.py`:gate→critique→judge(不变)后,新增 `diversify_select(evaluated, ui_n, buckets)` 产终端 20。
- `idea_eval/evaluate.py`:精排分融合 founder_fit 深评;打散按来源/边分桶。
- `config/`:新增 `funnel.json`(`recall_n/coarse_k/fine_k/ui_n` + 分桶配额 + founder_fit 子权重)。
- 因子契约不漂:`founder_fit` 两半共用同一纯函数(freqtrade 教训)。

## 4. 需要创始人拍的决策(见回复)
1. 切分量(默认 200/50/25/20)与分桶配额(英文≤8 / 中文≥10?)是否合适。
2. `founder_fit` 子权重(渠道独占 vs 人脉 vs 资本可行性 谁更重)。
3. 英文桶里 founder_fit 到底"次要加权"还是"完全不参与"(影响适合他的英文机会能否靠前)。
