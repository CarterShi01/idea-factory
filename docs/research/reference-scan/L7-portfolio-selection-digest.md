---
doc: research
lane: L7
title: "portfolio:组合选择与周报生成"
date: 2026-07-07
agent: subagent
---

# L7 portfolio:组合选择与周报生成

## 结论速览

Top 3:**fast-map-dpp**(Hulu NeurIPS'18 官方实现,单文件贪心 DPP-MAP,可抄成 stdlib 纯函数升级 `stages/portfolio/diversify.py` 的 `diversify_select`)、**horizon**(7.9k star 中英双语 AI 简报,周报 markdown 结构与多渠道投递范式直接可借,中文相关性强)、**git-cliff**(12k star 确定性报告生成器,"分组规则+模板全进配置、生成器零业务逻辑、零 LLM"的范式与 portfolio 段零新增 LLM 调用的铁律完全同构)。

最重要的发现:**本 lane 的三个子问题各有一个"冻结即可用"的最优源,且都不需要引依赖**——组合选择是一个 60 行的算法(DPP-MAP 贪心,我们 n≈100、k=20 的规模用 stdlib 就够);周报生成的正确范式是"配置驱动的确定性模板"而不是 LLM 写报告(Horizon 用 LLM 打分排序的部分恰是成本梯度反例,只借它的输出结构);跨周已投递去重不需要外部项目——feed 阅读器的 seen-GUID 状态库模式 + 本仓库已有的 append-only ledger 基建即可,登记外部源反而多余。

## 推荐候选(Top 2–3,按价值排序)

### fast-map-dpp
- repository: github.com/laming-chen/fast-map-dpp
- stars: ~130 · license: Apache-2.0 · 活跃度: 单作者,2020 年后冻结(last push 2020-05)——但它是 NeurIPS'18 论文(arXiv:1709.05135,Hulu 推荐团队,业界重排打散的标准引用)的官方实现,算法参考源冻结无害,正适合"钉 commit 镜像"
- mined_for:
  - 数据面: 无(纯算法仓,无 prompt/schema)
  - 机制面: ①质量×相似度核构造 `L = Diag(q)·S·Diag(q)`——把 eval_score 当 q、把我们已有的 `_jac`(Jaccard)当 S,一步把"分数高"和"彼此不像"统一进一个目标,替代现在 `diversify_select` 里 edge_cap+近重阈值的两段式启发;②Cholesky 增量更新的快速贪心 MAP 选择(O(k·n·d));③sliding-window 变体(长列表只要求相邻窗口内多样,可作为 20 条 UI 列表的"局部打散"选项)
- 挖什么: 仓库仅 `dpp.py`(核心贪心 + window 变体)与 `dpp_test.py`(核构造示例:score 向量 × 特征余弦相似度),两个文件全部读完即可;配套读 arXiv:1709.05135 的 Algorithm 1
- SKIP 什么: 无可 SKIP 的部分(仓库只有两个文件);不要顺着论文去引 DPP 生态的通用库(见 skip 清单 DPPy/apricot)
- 坑: 实现依赖 numpy 向量化;停更意味着 issue 无人答,遇到数值问题(核矩阵非正定)要自己加 jitter;论文场景是 n 上万,我们 n≈100,别被"fast"误导去搬优化技巧
- recommendation: adopt(抄纯函数:把贪心循环转写成 stdlib 列表运算,我们规模下性能无虞)
- 理由: 用一个 60 行的、有顶会背书的算法,把 `diversify_select` 的"配额+单边上限+Jaccard 阈值"三重启发收敛成单一可调目标(θ 一个参数控制"质量 vs 多样"),且配额(zh_min/en_max)仍可作为外层硬约束保留
- 与硬约束的冲突: numpy 依赖——裁剪方式:不引依赖,转写为纯 Python(k=20、n≈100 时 Cholesky 增量更新就是几个嵌套 for);成本梯度无冲突(纯代码,零 LLM,恰好符合 portfolio 段"零新增 LLM 调用"要求)

### horizon
- repository: github.com/Thysrael/Horizon
- stars: ~7.9k · license: MIT · 活跃度: 活跃(2026-07 仍在推送,GitHub Actions 自动化持续运行);单一主力作者(Thysrael)、自述"业余时间维护",需标记
- mined_for:
  - 数据面: 简报 markdown 的结构范式(每条=摘要+标签+可点击引用链接,正是我们周报"证据链接可点击"要的形态);sources/阈值/投递渠道的 JSON 配置 schema;GitHub Actions cron 产报+发布到 Pages 的 workflow 写法
  - 机制面: ①中英双语同报输出(对我们"14 中/6 英"混合组合的周报呈现直接相关,中国市场加分项);②投递渠道抽象(GitHub Pages/邮件/webhook 飞书/本地文件多路输出,一份 markdown 多处送达)——我们 `stages/portfolio/report.py` 目前只落盘,未来周报要送到创始人手上时这是现成蓝图;③fetch→dedup→score→enrich→summarize→deliver 的七段流水与我们八段架构互为印证
- 挖什么: 源配置 JSON 的字段设计(source 类型/阈值/schedule);briefing 输出模板与目录组织(按日归档,天然是"跨周历史"的文件布局);`.github/workflows/` 的 cron 产报流水;deliver 层各渠道 adapter 的接口切法
- SKIP 什么: AI 打分排序(0–10 LLM relevance score)与 LLM enrich/summarize 环节——前者违反成本梯度第一原则(让 LLM 做排序,而我们 portfolio 段必须零 LLM、rank 段必须是字段上的确定性代码),后者属 L5 lane 的领域;其 Python 运行时与 uv 依赖栈一概不 vendor
- 坑: 定位是"新闻雷达"而非决策报告,直接套模板会把周报写成资讯 digest——我们每条要带 verdict/证据链/48h 测试包,只借版式与投递,不借内容组织哲学;单作者业余维护,钉 commit 后再挖
- recommendation: concepts-borrow
- 理由: 中英双语、markdown 简报结构、多渠道投递三件事同时做对的项目仅此一个,且 MIT + 高热度 + 中文相关性满分
- 与硬约束的冲突: 核心排序靠 LLM(成本梯度冲突)——裁剪方式:只挖输出侧(模板/投递/配置 schema),排序侧继续用我们的确定性因子;联网投递是 opt-in 阶段的事,当前离线契约不受影响

### git-cliff
- repository: github.com/orhun/git-cliff
- stars: ~12k · license: MIT OR Apache-2.0(双许可,LICENSE-MIT + LICENSE-APACHE 并存) · 活跃度: 活跃(2026-07 仍在推送,规律发版);主作者 orhun 知名个人 + 多贡献者 + 赞助商,非单点风险
- mined_for:
  - 数据面: `examples/` 的 11 个渐进配置示例(minimal→detailed→statistics→keepachangelog…),展示同一引擎靠换配置产出完全不同报告——其中 `statistics.toml` 是"报告尾部附统计段"的现成样板,对应我们周报的"附录漏斗指标"
  - 机制面: "分组规则(regex `commit_parsers` → group 映射)+ 渲染模板(Tera)+ 排序/跳过规则全部进 TOML 配置,生成器本体零业务逻辑、完全确定性"的范式——我们 `stages/portfolio/report.py` 目前把 tier 命名(`_TIER_ZH`)、维度文案(`_JUDGE_DIM_ZH`)、段落结构全部硬编码在 Python 里,可提案迁到 config(与 funnel.json 同风格),让 decision_memos 与 weekly_report 成为"同一工件的两份渲染配置"
- 挖什么: 根目录 `cliff.toml`(默认配置的字段设计:header/body/footer 模板 + commit_parsers + sort/skip 规则);`examples/minimal.toml`、`examples/detailed.toml`、`examples/statistics.toml`(渐进复杂度,看配置面如何分层);website 文档的 configuration 章节(字段语义)
- SKIP 什么: 全部 Rust 运行时代码(`git-cliff-core/`、`git-cliff/`,不可抄进 Python 也无必要);git 集成层(我们的输入是 verdicts.json/screened.json 不是 commit 历史);npm/pypi 打包与 Docker 发行
- 坑: 这是范式迁移不是代码迁移——一行都抄不了;它的模板语言是 Tera(Jinja2 系),千万别为此引 Jinja2(stdlib 铁律),用 `string.Template` 或保持 Python 渲染函数,只借"配置驱动分组 + 确定性渲染 + 示例配置分层"的切法
- recommendation: concepts-borrow
- 理由: 它是"零 LLM、纯确定性、配置即报告"这一范式在开源里最成熟、最被验证的标本,与 portfolio 段"零新增 LLM 调用"铁律完全同构,而周报恰是我们最需要防止"顺手让 LLM 写"的地方
- 与硬约束的冲突: 无(确定性零 LLM 正是它的卖点;唯一注意点是不为模板引擎引新依赖,已在坑中说明)

## 评估过但不推荐(skip 清单,防重爬)

- dppy(github.com/guilgautier/DPPy)— skip:通用 DPP 采样工具箱(240★,MIT),面向科研采样而非 top-k 选择,numpy/scipy 依赖重且 2024 年后基本停更;fast-map-dpp 的 60 行贪心已覆盖需求
- apricot(github.com/jmschrei/apricot)— skip:子模优化选型全(534★,MIT,尚在维护)但 numba+numpy 编译栈重、面向百万级样本的 facility-location 场景;我们 n≈100 用不上,概念上被 DPP-MAP 覆盖
- pyportfolioopt(github.com/PyPortfolio/PyPortfolioOpt,原 robertmartin8 名下)— skip:5.8k★ 金融均值-方差组合优化,"portfolio"仅名字同源——协方差矩阵/有效前沿的前提是收益时序,idea 组合没有,方法论不可映射
- release-please(github.com/googleapis/release-please)— skip:7.1k★ 但与 GitHub PR/Release 流程深度耦合,可借的"conventional commits 分组"部分 git-cliff 已覆盖且配置化更纯
- conventional-changelog(github.com/conventional-changelog/conventional-changelog)— skip:8.5k★ Node monorepo,同范式下 git-cliff 的配置化更彻底,无增量可挖
- trendradar(github.com/sansan0/TrendRadar)— skip:60k★ 中文热点聚合+多渠道推送,中国相关性满分,但 **GPL-3.0**(只能借概念不能抄代码),且主体属 L1 recall 领域;其投递渠道概念 Horizon(MIT)已覆盖
- meridian(github.com/iliane5/meridian)— skip:2.4k★ AI 情报简报,LLM 全程打分+撰写(成本梯度反例的完整体),Cloudflare Workers 栈绑定,2025-05 后停更
- miniflux(github.com/miniflux/v2)— skip:9.4k★ feed 阅读器,其 entry-hash 判重模式一句话即吸收(条目哈希入库、重见即跳过),Go+Postgres 运行时无可挖资产;我们 ledger/impressions 已是对应基建
- rss2email(github.com/rss2email/rss2email)— skip:seen-GUID 状态文件模式同上一句话吸收;**GPL-2.0** 且低热度
- 小型 DPP/MMR 论文复现仓(github.com/mbp28/determinantal-point-processes、github.com/ChengtaoLi/dpp、github.com/stepgazaille/mmr)— skip:无维护的课程级/naive 实现,权威性与代码质量均低于官方 fast-map-dpp
- keila(github.com/pentacent/keila)— skip:自托管 newsletter **发送平台**(Elixir),解决的是"发邮件的服务"不是"生成报告的范式",触碰本项目"不部署服务"非目标

## 本 lane 的搜索方法沉淀

- **最有效入口**:①GitHub REST API 直查候选 repo(`api.github.com/repos/<org>/<repo>`,一次拿全 stars/license/pushed_at/archived,比搜索页可靠且快,适合 miner skill 做"现状核验"步骤);②从论文反查官方实现(arXiv:1709.05135 → fast-map-dpp),权威性判断一步到位;③GitHub topic 页(`determinantal-point-processes`、`weekly-digest`、`newsletter`)做候选池扩展。
- **死胡同一:金融词汇陷阱**。"portfolio construction/optimization/selection" 检索出来全是量化金融仓(PyPortfolioOpt 系),与本段"idea 组合"语义完全不通;正确的检索语言是推荐系统术语——"diversified re-ranking"、"result diversification"、"MMR DPP re-rank"。
- **死胡同二:newsletter≠digest**。"newsletter automation/tool" 搜出的多是发送平台(listmonk/keila,服务型,非目标),报告生成范式要搜 "digest generator"、"briefing"、"changelog generator";确定性报告范式最好的样本反而在 changelog 工具族(git-cliff)里,不在 newsletter 族里。
- **死胡同三:已投递去重不需要外部源**。feed 阅读器的 seen-GUID/entry-hash 模式(rss2email/miniflux)一句话就能吸收,专门登记参考源是浪费——直接消费本仓库 `data/ledger/impressions` 即可实现跨周判重。
- **中文向经验**:中文 AI 简报仓(Horizon/TrendRadar)是"中文渠道呈现+多路投递"最好的参考池,但普遍 LLM-heavy(用 LLM 打分排序),挖时一律"只挖输出侧、不挖排序侧";另注意这族仓 GPL 比例偏高,license 先查再挖。
