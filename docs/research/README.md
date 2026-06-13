# Idea Factory × Idea-Evl 调研报告集（2026-06-13）

本目录是一次多 Agent 全网调研的产出。目标：为「基于 LLM agent 技术，从 **外部事件变化 + 个人迸发的 idea + 模拟人群痛点分析** 三个源头，每天稳定产出 10~20 条经初筛的靠谱创业 idea」这一系统，调研可参考的开源项目、框架、方法论与商业格局，并给出落地路线。

调研由 10 个并行 agent（各负责一个层面）+ 1 个综合 agent 完成。

## 阅读顺序

**先读 [`00-executive-summary-and-roadmap.md`](00-executive-summary-and-roadmap.md)** —— 一页执行摘要 + 分阶段落地路线图，是所有分报告的综合。其余按需查阅。

| # | 报告 | 一句话结论 |
|---|------|-----------|
| 00 | [执行摘要与落地路线图](00-executive-summary-and-roadmap.md) | 综合全部发现，给出系统蓝图 + 分阶段路线图 |
| 01 | [idea 生成/发现的开源项目与产品](01-idea-generation-discovery-projects.md) | 存在高度对齐的开源仓库 `idea-validation-agents`，但**不建议整体 fork，逐文件借鉴** |
| 02 | [Agent 编排框架选型](02-agent-orchestration-frameworks.md) | 一人公司场景下倾向轻量编排，警惕「复杂多 agent 框架」非目标 |
| 03 | [从量化投资借鉴范式](03-quant-investing-paradigms.md) | 信号→因子→打分→回测→组合→风控，可整套映射到选 idea |
| 04 | [外部信号源与趋势检测](04-external-signal-sources-and-trend-detection.md) | Reddit/HN/PH/GitHub/Trends 优先级清单 + 合规注意 |
| 05 | [痛点挖掘与人群模拟](05-painpoint-mining-persona-simulation.md) | 第 3 源头：从真实抱怨挖痛点 + persona 模拟的 schema 与 prompt |
| 06 | [Idea 评估与打分方法论](06-idea-evaluation-methodology.md) | idea-evl 的多维 rubric + LLM-as-judge + 对抗式批判设计 |
| 07 | [自动化创意/假设生成（学术）](07-automated-idea-hypothesis-generation.md) | 保证多样性/新颖度、防 mode collapse 的方法 |
| 08 | [商业 SaaS 竞品与市场格局](08-commercial-saas-competitors.md) | Exploding Topics / IdeaBrowser / GummySearch 等格局与差异化机会 |
| 09 | [系统架构、记忆与数据设计](09-system-architecture-memory-data.md) | 从离线 demo 演进到「每日产出」的工程蓝图 |
| 10 | [一人公司/独立开发者工作流](10-indie-solopreneur-idea-workflow.md) | 每天 30-60 分钟人工介入消化 idea flow 的协作流 |

## 核心结论（TL;DR）

1. **没有可直接 fork 的端到端底座**，但 `MaxKmet/idea-validation-agents` 的「评分算法 + 验证清单」最值得逐文件借鉴。
2. **量化投资范式高度可迁移**：把 idea 当作「标的」，做因子化打分、时效衰减、事后回测验证「靠谱」。
3. **信号源集中在真实社区抱怨**（Reddit/HN/App Store），优于问卷；注意 API 商用合规（GummySearch 因此关停）。
4. **idea-factory 管生成、idea-evl 管评估**：评估侧用 5 维加权 + 致命短板一票否决，产出「分数 + 决策备忘」双产物。
5. **守住非目标**：不因小任务引入 web UI / DB / 复杂多 agent 框架，按路线图分阶段推进。

> 报告中的链接均来自调研期间的真实搜索结果；事实性结论请在采用前自行复核。
