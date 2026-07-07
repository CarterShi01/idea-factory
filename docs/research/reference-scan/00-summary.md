---
doc: research-summary
title: "Reference Scan 汇合报告:10-lane 开源参考调研结果"
date: 2026-07-07
agent: main-session
related: [00-brief.md]
---

# Reference Scan 汇合报告

> 10 个 lane 报告(L1–L10)已全部落盘本目录。本文按任务书 §6.4 汇合:
> 全局 Top 10 推荐表、候选 `sources.yaml` 草稿、全局 skip 清单、待创始人拍板事项。
> 每个候选的"挖什么/坑/裁剪方式"细节以对应 lane 文件为准,本文只做索引与排序。

## 0. 一页结论

- **30 个推荐候选**(12 adopt + 18 concepts-borrow),全部通过"只挖不跑"评估;
  无一需要立即引依赖(唯一的依赖申请候选是 trafilatura,见 §4)。
- **跨 lane 最大发现**:`traces.jsonl` 目前不记 token/cost——**成本梯度第一原则
  无法度量**(L10)。这是所有报告里唯一指向"我们自己刻度缺失"的发现,建议最高
  优先落地(借 OpenInference 的 `llm.token_count.*`/`llm.cost.*` 字段名 + litellm
  价格表数据)。
- **我们的设计被多处独立印证**:rank 段机制在 Twitter 生产系统逐件有同构先例
  (L4);enforce_citation 有 DeepMind SAFE 权威先例(L6);"过量产出→筛选"与
  学术 ideation 流水线完全同构(L3);"每段落盘工件"与 datatrove 四阶段 dedup
  同构(L2)。方向不用改,补机制即可。
- **两个"生态空白"确认自研正确**:中文招聘/社区采集无可登记维护仓,自建 adapter
  是唯一路径(L1);"读文件、无数据库的 web 漏斗仪表盘"无开源先例,studio 继续
  自研,只挖 schema(L10)。
- **License 雷区比预期大**:明星仓 ≠ 可抄。MediaCrawler(NC)、SakanaAI(RAIL)、
  twitter-the-algorithm(AGPL)、pybroker(Commons Clause)、phoenix(ELv2)全部
  只能概念级重写;**登记源时必须逐仓读 LICENSE 原文**(GitHub 显示 "Other" 的
  一律人工核验)。

## 1. 全局 Top 10 推荐表(价值 × 可挖性 × 硬约束兼容度)

| # | id | lane | license | rec | 一句话价值 |
|---|---|---|---|---|---|
| 1 | fast-map-dpp | L4+L7 双推 | Apache-2.0 | adopt | ~60 行贪心 MAP DPP,手工移植为 stdlib 纯函数,同时升级 rank 段 select 与 portfolio 段 diversify 的多段启发式为单一可调目标 |
| 2 | json-repair | L9 | MIT | adopt | 零依赖纯 Python 的 LLM JSON 修复解析器,直接补上 extract_json 正则失手即整条报废的痛点;含 schema 引导修复 |
| 3 | promptfoo | L6 | MIT | adopt | `src/prompts/grading.ts` 单文件 7 个工业级评审 prompt(枚举裁决/agentic 取证/防注入),OpenAI evals 官方迁移目的地 |
| 4 | crawl4ai | L5 | Apache-2.0 | adopt | "LLM 对页面模板只花一次钱生成抽取 schema,之后纯代码确定性抽取"——全场唯一与成本梯度同构的现成设计;prompts.py 即证据结构化骨架 |
| 5 | gpt-researcher | L5 | Apache-2.0 | adopt | deep-research 事实标准;curate_sources prompt 明文"优先含数字来源",与证据门天然对齐;多后端 scraper 注册表与 channels 同构 |
| 6 | deepeval | L6 | Apache-2.0 | adopt | G-Eval 固定 evaluation_steps 提高 judge 重跑一致性;DAG 决策树(便宜二值判定在前、贵评分在分支)与 gate→judge 同构 |
| 7 | langfuse | L10 | MIT(ee/ 除外) | adopt | Score/ScoreConfig/annotation-queue schema 逐字段映射 verdicts.jsonl;source 枚举(API\|EVAL\|ANNOTATION)升级"操作即标签" |
| 8 | hf-datatrove + simhash-1e0ng + ekzhu-datasketch | L2 | Apache/MIT/MIT | 混合 | MinHash-LSH 四阶段管线 + 纯 stdlib SimhashIndex(跨周 seen 库)+ 阈值→(b,r) 推导函数;三仓合治 triage 规模化 |
| 9 | noviscl-ai-researcher | L3 | MIT | adopt | 斯坦福 79 人盲评论文官方仓,"过量产出→去重→锦标赛→过滤"prompt 骨架可抄;pairwise>直接打分的结论借给 diligence |
| 10 | jobspy + google-play-scraper | L1 | MIT/MIT | adopt | JobPost schema(salary 三元组=付薪强度)与差评字段直接 promote 成 fixture 字段规范;零依赖请求构造可抄成 stdlib 纯函数 |

**Top 10 之外仍强烈建议登记**(细节见 lane 文件):twitter-the-algorithm(L4,
AGPL 只借概念但概念含金量全场最高)、instructor + litellm(L9,reask 闭环 +
错误分类重试/冷却/降级链)、fatebook + uncertainty-toolbox(L8,回流闭环与
切片校准)、trafilatura(L5,htmldate 日期提取直接服务 24 个月红线)、
chats-lab-verbalized-sampling(L3,我们在用的 VS 方法的上游权威源)、
git-cliff + horizon(L7,零 LLM 配置驱动报告 + 中英双语投递)、
openinference + label-studio(L10,trace 字段名与标注元数据)、
changedetection-io(L1,增量监测判定逻辑)、media-crawler(L1,NC,CDP 合规
抓取模式)、microsoft-qlib(L4,因子库防漂移工程)、verdict(L6,judge 原语
分类学)、sakana-ai-scientist(L3,RAIL,反思早停/存档防重/新颖性判决回路)、
dvclive(L8,文件即真相目录约定)。

## 2. 候选 sources.yaml 草稿

> 字段:id / repository / license / lanes / status(adopt|concepts-borrow)/
> mined_for(数据面 d / 机制面 m)/ pin(是否必须钉 commit)。正式登记时补
> commit hash 与 per-source 挖矿要点(从 lane 文件"挖什么"一节转录)。

```yaml
sources:
  # ---- 算法/纯函数可抄(adopt) ----
  - id: fast-map-dpp
    repository: github.com/laming-chen/fast-map-dpp
    license: Apache-2.0
    lanes: [rank, portfolio]
    status: adopt
    mined_for: {m: greedy-MAP-DPP 纯函数(dpp.py 全文)}
    pin: true   # 冻结仓,钉最终 commit
  - id: json-repair
    repository: github.com/mangiucugna/json_repair
    license: MIT
    lanes: [llm-infra]
    status: adopt
    mined_for: {m: 容错 JSON 解析 + schema 引导修复 → runtime/jsonfix.py}
    pin: true
  - id: simhash-1e0ng
    repository: github.com/1e0ng/simhash
    license: MIT
    lanes: [triage]
    status: adopt
    mined_for: {m: SimhashIndex 分块索引(跨周 seen 库增量查重)}
    pin: true   # 单作者停更,抄入自养
  - id: hf-datatrove
    repository: github.com/huggingface/datatrove
    license: Apache-2.0
    lanes: [triage]
    status: concepts-borrow
    mined_for: {d: MinHash 默认参数(14x8,阈值≈0.72)→funnel.json, m: 四阶段 dedup 管线}
    pin: true
  - id: ekzhu-datasketch
    repository: github.com/ekzhu/datasketch
    license: MIT
    lanes: [triage]
    status: concepts-borrow
    mined_for: {m: _optimal_param 阈值→(b,r) 推导(scipy 积分换 stdlib)}
    pin: true   # v2.0.0 刚换置换方案,跨版本指纹不可比
  # ---- prompt/schema 资产(adopt) ----
  - id: promptfoo
    repository: github.com/promptfoo/promptfoo
    license: MIT
    lanes: [diligence]
    status: adopt
    mined_for: {d: src/prompts/grading.ts 全部评审 prompt + G-Eval 两条}
    pin: true   # 被 OpenAI 收购,路线可能漂移
  - id: deepeval
    repository: github.com/confident-ai/deepeval
    license: Apache-2.0
    lanes: [diligence]
    status: adopt
    mined_for: {d: g_eval/template.py 两段式模板, m: DAG 决策树评审}
    pin: true
  - id: gpt-researcher
    repository: github.com/assafelovic/gpt-researcher
    license: Apache-2.0
    lanes: [enrich]
    status: adopt
    mined_for: {d: gpt_researcher/prompts.py(curate_sources 等), m: scraper 多后端注册表 + per-step 模型分配}
    pin: true
  - id: crawl4ai
    repository: github.com/unclecode/crawl4ai
    license: Apache-2.0
    lanes: [enrich]
    status: adopt
    mined_for: {d: crawl4ai/prompts.py(schema 抽取/内容过滤), m: 两步 schema 抽取范式 + pruning/BM25 过滤纯函数}
    pin: true   # 0.x API 破坏性变更频繁
  - id: noviscl-ai-researcher
    repository: github.com/NoviScl/AI-Researcher
    license: MIT
    lanes: [generate]
    status: adopt
    mined_for: {d: grounded_idea_gen.py prompt 骨架 + filter/novelty prompt, m: 批内防重护栏 + n-gram 去重纯函数}
    pin: true   # 论文配套冻结仓
  - id: chats-lab-verbalized-sampling
    repository: github.com/CHATS-lab/verbalized-sampling
    license: Apache-2.0
    lanes: [generate]
    status: adopt
    mined_for: {d: VS 官方 prompt 措辞 + k/tau 默认参数}
    pin: false  # 持续跟踪方法演进
  - id: jobspy
    repository: github.com/speedyapply/JobSpy
    license: MIT
    lanes: [recall]
    status: adopt
    mined_for: {d: JobPost schema → jobs.jsonl 字段规范, m: per-site scraper 结构 + salary/date 归一化纯函数}
    pin: true
  - id: google-play-scraper
    repository: github.com/JoMingyu/google-play-scraper
    license: MIT
    lanes: [recall]
    status: adopt
    mined_for: {d: reviews 字段(score 支持 1–3 星筛选), m: 零依赖请求构造 + continuation 分页}
    pin: true   # 2024-06 停更,钉 commit 自担维护
  - id: langfuse
    repository: github.com/langfuse/langfuse
    license: MIT   # ee/ 目录商业 license,挖矿必须路径过滤
    lanes: [observability]
    status: adopt
    mined_for: {d: Score/ScoreConfig/annotation-queue schema, m: source 枚举 + 标注队列交互}
    pin: true
  # ---- 概念/模式借鉴(concepts-borrow) ----
  - id: twitter-the-algorithm
    repository: github.com/twitter/the-algorithm
    license: AGPL-3.0   # ⚠️ 绝不可抄代码
    lanes: [rank]
    status: concepts-borrow
    mined_for: {m: 乘性位置衰减打散公式 + 负权重融合 + scaling-scorer 组件栈(founder_fit 先例)}
    pin: true   # 冻结快照
  - id: microsoft-qlib
    repository: github.com/microsoft/qlib
    license: MIT
    lanes: [rank]
    status: concepts-borrow
    mined_for: {m: 因子=声明式表达式+算子单一真相源(ops.py/Alpha158 组织方式)}
    pin: false
  - id: instructor
    repository: github.com/567-labs/instructor
    license: MIT
    lanes: [llm-infra]
    status: concepts-borrow
    mined_for: {m: reask 闭环(core/retry.py)+ Mode 分层 + 异常分类}
    pin: true   # v1.9–1.10 大重构过
  - id: litellm
    repository: github.com/BerriAI/litellm
    license: MIT   # enterprise/ 目录商业条款,绕开
    lanes: [llm-infra]
    status: concepts-borrow
    mined_for: {d: model_prices_and_context_window.json → config/llm/prices.json, m: 错误分类 RetryPolicy + 冷却 + fallback 链(方向必须贵→便宜)}
    pin: true
  - id: fatebook
    repository: github.com/Sage-Future/fatebook
    license: MIT
    lanes: [retro]
    status: concepts-borrow
    mined_for: {m: Brier/相对 Brier/校准图分桶(lib/_scoring.ts)+ resolve 三态生命周期(YES/NO/AMBIGUOUS+到期提醒)}
    pin: false
  - id: uncertainty-toolbox
    repository: github.com/uncertainty-toolbox/uncertainty-toolbox
    license: MIT
    lanes: [retro]
    status: concepts-borrow
    mined_for: {m: miscalibration area + adversarial group calibration(按 persona/channel 切片)+ interval score}
    pin: true   # 活跃度放缓,当冻结公式书用
  - id: dvclive
    repository: github.com/iterative/dvclive
    license: Apache-2.0
    lanes: [retro]
    status: concepts-borrow
    mined_for: {m: 文件即真相目录约定(summary json + append-only tsv + params 快照)}
    pin: false
  - id: trafilatura
    repository: github.com/adbar/trafilatura
    license: Apache-2.0   # ≥v1.8;更早版本 GPL,只看新版
    lanes: [enrich]
    status: concepts-borrow   # live 获批时升 adopt-as-dependency
    mined_for: {m: 正文抽取启发式 + 姊妹仓 htmldate 日期提取(服务 24 月红线)}
    pin: true
  - id: verdict
    repository: github.com/haizelabs/verdict
    license: MIT
    lanes: [diligence]
    status: concepts-borrow
    mined_for: {m: judge 原语分类学(whitepaper)+ 边界样本加验证层的裁剪思路}
    pin: true   # 活跃度存疑
  - id: sakana-ai-scientist
    repository: github.com/SakanaAI/AI-Scientist
    license: RAIL-derived   # ⚠️ 非标 license,概念级重写
    lanes: [generate]
    status: concepts-borrow
    mined_for: {m: 反思早停回路 + 想法存档防重(零额外调用)+ 新颖性判决字符串由代码解析}
    pin: true
  - id: git-cliff
    repository: github.com/orhun/git-cliff
    license: MIT OR Apache-2.0
    lanes: [portfolio]
    status: concepts-borrow
    mined_for: {d: examples/*.toml 渐进配置样板(statistics.toml=漏斗指标附录), m: 分组规则+模板全进配置、生成器零业务逻辑}
    pin: false
  - id: horizon
    repository: github.com/Thysrael/Horizon
    license: MIT
    lanes: [portfolio]
    status: concepts-borrow
    mined_for: {d: 中英双语简报 markdown 结构 + 渠道配置 schema, m: 多渠道投递抽象;⚠️ LLM 排序部分是成本梯度反例,只挖输出侧}
    pin: true   # 单作者业余维护
  - id: changedetection-io
    repository: github.com/dgtlmoon/changedetection.io
    license: Apache-2.0
    lanes: [recall]
    status: concepts-borrow
    mined_for: {m: 抓取→过滤→diff→trigger 的事件化判定逻辑 + restock/价格 processor;lxml 换 stdlib 重写}
    pin: false
  - id: media-crawler
    repository: github.com/NanmiCoder/MediaCrawler
    license: NC-custom   # ⚠️ 非商用,一行代码不能进仓
    lanes: [recall]
    status: concepts-borrow
    mined_for: {m: CDP 挂已登录浏览器合规抓取模式 + 每平台一目录 adapter 结构 + 中文平台靶点清单}
    pin: false  # 只读设计文档,无代码镜像
  - id: openinference
    repository: github.com/Arize-ai/openinference
    license: Apache-2.0
    lanes: [observability]
    status: concepts-borrow
    mined_for: {d: spec/semantic_conventions.md 字段命名(llm.token_count.*/llm.cost.*/span kind)}
    pin: true
  - id: label-studio
    repository: github.com/HumanSignal/label-studio
    license: Apache-2.0
    lanes: [observability]
    status: concepts-borrow
    mined_for: {d: annotation 元数据字段(lead_time/was_cancelled/ground_truth), m: predictions/annotations 二元结构 → 系统预测 vs 人工纠正的免费校准数据}
    pin: false
  # ---- watch 项(暂不登记,定期回看) ----
  - id: otel-genai-semconv
    repository: github.com/open-telemetry/semantic-conventions-genai
    license: Apache-2.0
    lanes: [observability]
    status: watch   # Development 状态零 release,stable 后评估从 OpenInference 迁移命名
```

## 3. 全局 skip 清单(合并,按理由分类;逐条一句话理由见各 lane 文件)

- **License 禁区(代码一行不能碰)**:rsshub(AGPL)、firecrawl(AGPL+云绑定)、
  searxng(AGPL+常驻服务)、trendradar(GPL)、rss2email(GPL)、freqtrade
  (GPL;教训已内化,两个 lane 独立确认无新增可挖)、pybroker(Commons Clause
  禁商用)、phoenix(ELv2+专利声明)。
- **重运行时/云绑定("跑起来才有价值")**:ossinsight、nvidia-nemo-curator、
  gorse(且新主打 LLM reranker,成本梯度诱导源)、recommenders、
  open-deep-research(langchain 系)、auto-deep-research、scrapegraph-ai、
  markitdown(不对口)、mlflow、aim、sacred、trackio、keila、opik、argilla
  (官方维护模式)、doccano、lmnr、helicone、datasette、guardrails、gateway、
  outlines(约束解码对远程 API 后端不适用)、baml(Rust 核心)、routellm。
- **停更/坟场**:openai-evals(2026-11-30 关停,资产已被 promptfoo 吸收)、
  chateval、multi-agents-debate、judgelm、pandalm(微调 judge 路线正交)、
  prometheus-eval、fortuna(archived)、guildai、properscoring(继任者
  scoringrules 记为未来概率化预测时的备选)、dzhng/deep-research(最小范本
  可读但不登记)、text-dedup(资产被 datatrove/datasketch 覆盖)、
  mattilyra-lsh、duplodocus、bosszp 家族(毕设级)、facundoolano 双 scraper、
  storm、nova(无代码)、genspark/deepmind co-scientist(闭源)。
- **过度工程/不匹配**:thefuzz/rapidfuzz(C++ 核心)、rensa(Rust)、
  dedupeio-dedupe、venmo-business-rules、py-rules-engine、json-rules-engine、
  semhash(本体依赖嵌入栈;DeduplicationResult schema 概念已吸收)、
  dppy、apricot、pyportfolioopt(金融同名陷阱)、release-please、
  conventional-changelog、meridian、miniflux(entry-hash 一句话吸收)、
  kunquant、quantaalpha、alphalens(IC 分析概念留给 retro)、
  k-dpp-reco-engine、dpp-map-inference、fun-rec、mapie(只借 n≥1/α−1 公式)、
  metaculus-forecasting-tools(主体归 L5/L6)、jamesponddotco-llm-prompts
  (浅模板方向整体死胡同)、hkuds-ai-researcher、agent-laboratory、coi-agent
  (备选,需要第二 pairwise 参照时回捞)、simonw/llm、promptlayer、prompty、
  langsmith(闭源)、lnav、klp、jobclaw、mohammedcha-gplay-scraper、
  nickscamara/open-deep-research、gharchive(数据服务直接消费,无需登记仓)。

## 4. 需要创始人拍板的事项

1. **依赖申请(唯一一个)**:live fetcher 获批时,trafilatura(+lxml)是否作为
   单个轻依赖引入(L5)。近期替代方案:先抄 htmldate 日期启发式与正文抽取
   启发式为纯函数,零依赖。
2. **抄入代码的批准**(均为 MIT/Apache 纯函数级,按 CLAUDE.md 仍需点头):
   json-repair(~200–400 行 → `runtime/jsonfix.py`)、simhash(~200 行)、
   fast-map-dpp(~60 行)、datatrove MinHash 管线(<150 行)。
3. **License 灰区执行纪律**:AGPL/NC/RAIL 三类源(twitter/MediaCrawler/Sakana)
   确认"只读设计文档与公式、重新表述后自写实现、不做逐行改写"的边界;未来
   miner skill 对这三类源禁用"镜像代码"步骤。
4. **live 抓取合规**:中文源采集采用"CDP 挂创始人已登录浏览器、只读公开页、
   低频"模式(MediaCrawler 概念)是否可接受;涉及平台 ToS 风险自担。
5. **机制提案优先级**(各 lane 已给出、需要排期的 top 项):
   ① trace 补 token/cost 字段(L10,成本梯度可观测的前提);
   ② 结构化输出三层闭环:schema 真校验→reask→修复解析(L9);
   ③ judge 评分步骤显式锚定 + 枚举裁决(L6,注意 dify/flows 镜像同步);
   ④ outcomes 补 AMBIGUOUS 三态 + 到期未 resolve 提醒(L8);
   ⑤ verdicts/标签补 source 枚举 + lead_time/was_cancelled(L10)。

## 5. 搜索方法全局沉淀(供未来 miner skill)

- **现状核验标准动作**:`api.github.com/repos/<org>/<repo>` 一次拿全
  stars/license/pushed_at/archived;license 显示 "Other" 必读 LICENSE 原文
  (pybroker/MediaCrawler/Sakana 三个雷都靠这步排出)。
- **资产定位捷径**:prompt 几乎总在 `prompts.py`/`src/prompts/`;数据模型看
  官方 docs 的 "data model" 页快于读源码;大仓先走社区 awesome 注解仓
  (igorbrigadir/awesome-twitter-algo)再定位文件;`raw.githubusercontent.com`
  直读单文件替代 clone。
- **通用死胡同**(各 lane 独立撞过,未来不必再爬):泛搜"lightweight/pure
  python X"(描述不可信,必须开源码验证)、"business idea generation"(浅模板
  海)、"newsletter automation"(全是发送平台)、"portfolio selection"(金融
  同名陷阱)、"no database dashboard"(无先例)、multi-agent debate 仓
  (2023–24 论文代码坟场)。
- **钉 commit 优先级**:反爬对抗型(L1)与 prompt 快速迭代型(promptfoo/
  crawl4ai/gpt-researcher)必须钉;冻结算法仓(fast-map-dpp/noviscl)钉最终
  commit 即一劳永逸;活跃演进型(datasketch v2 换置换方案)跨版本资产不可比,
  镜像后 diff 追踪。
