---
doc: research
lane: L8
title: "retro:校准、回测与实验记录"
date: 2026-07-07
agent: subagent
---

# L8 retro:校准、回测与实验记录

## 结论速览

Top 3:**fatebook**(MIT,活跃)是"预测→到期提醒→resolve YES/NO/AMBIGUOUS→Brier/相对 Brier/校准图"完整回流闭环的最佳开源先例,算法层可整套借;**uncertainty-toolbox**(MIT,2k stars)提供校准指标目录(miscalibration area、adversarial group calibration、sharpness)和 isotonic recalibration,公式全部可 stdlib 重写;**dvclive**(Apache-2.0,活跃)验证了"纯文本文件即实验追踪真相"的目录约定(summary json + append-only tsv 序列 + 静态报告),与本仓 ledger/jsonl 哲学同构,借布局即可。

最重要的一个发现:**"样本不足明确拒绝"这条我们已有的红线,在开源界有两个可升级的严谨范式**——(a) split conformal prediction 给出无分布假设的显式最小样本公式(覆盖率 1−α 至少需要 n ≥ 1/α − 1 条校准样本,MAPIE 是参考实现);(b) 量化回测圈用 bootstrap 置信区间代替硬阈值(相关系数 CI 跨零即拒绝,样本越少区间自然越宽,pybroker 有实现但 Commons Clause 只能借思想)。两者都是教科书算法,可在 `calibrate.py` 里 stdlib 手写,不需要引任何依赖。

## 推荐候选(Top 3,按价值排序)

### fatebook
- repository: github.com/Sage-Future/fatebook
- stars: ~59 · license: MIT · 活跃度: 活跃(last push 2026-06,open issues 37);Sage(EA 系 501c3)团队维护,非单作者
- mined_for:
  - 数据面: 无(TypeScript + Prisma/Postgres,代码本体不可 promote)
  - 机制面: 完整的"预测日志→到期提醒→resolve→记分→校准图"产品闭环 + 三个具体算法:①Brier 记分 `(forecast−outcome)² + ((1−forecast)−(1−outcome))²`;②**相对 Brier**(个体分减去同期全体中位数分,把"题目本身难不难"归一化掉);③校准图 10 等宽分桶(`floor(p*10)`,x=桶中心,y=桶内 YES 实际频率,不平滑,且过滤同一用户 1 分钟内重复预测)
- 挖什么:
  - `lib/_scoring.ts` — Brier / 相对 Brier / 按天区间的时间加权预测均值(线性插值)与聚合逻辑,全是初等公式,直接翻译成 stdlib Python
  - `pages/api/calibration_graph.ts` — 校准图分桶与去噪规则
  - `components/TrackRecord.tsx` / `components/CalibrationChart.tsx` — retro 报告该展示什么(Brier、相对 Brier、校准曲线、按 tag 切片)的 UI 信息架构,喂给 studio 四视图
  - 问题生命周期模型(prisma schema 中 Question/Forecast/Resolution):resolve 三态 **YES/NO/AMBIGUOUS + 到期 email 提醒**——我们 `outcomes.jsonl` 目前只有"已记录"一态,缺"到期未 resolve 提醒"和"AMBIGUOUS(测试作废)"状态,这是对 `stages/retro/outcomes.py` 最直接的机制提案
- SKIP 什么: 整个 Next.js/Prisma/Postgres/Slack-bot 运行时(与"不引数据库服务"直接冲突);tournament/leaderboard 多人功能(我们单创始人场景用不上)
- 坑: 记分逻辑按"每日区间×多预测者中位数"设计,单人使用时相对 Brier 退化为 undefined(源码里已显式处理)——移植时相对基线要换成"历史自身滚动中位数"或跳过;算法藏在 web app 源码里,没有独立库文档,只能读源码挖
- recommendation: concepts-borrow
- 理由: 任务书问的"预测→实际→教训回流闭环有没有开源先例"——这就是那个先例,且 MIT、活跃、算法初等
- 与硬约束的冲突: 技术栈全不同(TS/Postgres),但因为只借算法与生命周期设计、公式手写为 stdlib 纯函数,无实质冲突

### uncertainty-toolbox
- repository: github.com/uncertainty-toolbox/uncertainty-toolbox
- stars: ~2.0k · license: MIT · 活跃度: 放缓(last push 2025-03,约 16 个月前),CMU 学术团队出品、被 UQ 社区广泛引用,数学内容不腐烂
- mined_for:
  - 数据面: 无(numpy/scipy 依赖,不能直接 vendor)
  - 机制面: 面向**回归/数值预测**的校准指标目录与再校准范式——比二元 Brier 更贴我们的 `prediction_error`(smoke-test 数值 target vs actual)场景
- 挖什么:
  - `uncertainty_toolbox/metrics_calibration.py` — mean absolute calibration error、miscalibration area(校准曲线偏离对角线的面积,单数字概括"预测区间可不可信")、**adversarial group calibration**(找校准最差的子群)——后者直接映射成我们的机制提案:retro 按 channel/persona 切片算校准,专门盯 `confidence=synthetic` 的模拟人群信号是否系统性过度自信(与 CLAUDE.md"personas are suspect"原则闭环)
  - `uncertainty_toolbox/metrics_scoring_rule.py` — interval score / check score 公式(未来给 idea 预测加区间时的记分规则)
  - `uncertainty_toolbox/recalibration.py` — isotonic regression 再校准的接线方式(只看模式:再校准是"读历史→输出修正映射→人工决定是否采用",与我们 calibrate 只读不写的立场一致)
  - README 的 glossary/教学图 — 给 `docs/` 写 retro 指标说明时的 rubric 蓝本
- SKIP 什么: `viz.py`(matplotlib 依赖,studio 用自己的前端画);任何 sklearn/scipy 接口封装;不要 pip install,全部公式手写
- 坑: 指标假设有"预测均值+预测标准差"成对输入,而我们目前只有点预测——落地前要先让 diligence/judge 产出区间或置信度字段,否则大半指标没有输入;活跃度在放缓,当作"冻结的公式参考书"用而非跟踪上游
- recommendation: concepts-borrow
- 理由: 回归向校准指标最全、解释最好的 MIT 参考书,每个指标都是几十行初等数学,stdlib 可写
- 与硬约束的冲突: numpy/scipy 依赖 → 裁剪方式:只抄公式重写为纯 Python(与 `calibrate.py` 里现成的 stdlib `_pearson` 同风格),不引依赖

### dvclive
- repository: github.com/iterative/dvclive
- stars: ~195 · license: Apache-2.0 · 活跃度: 活跃(last push 2026-06),iterative.ai 公司维护
- mined_for:
  - 数据面: 无
  - 机制面: "文件即真相"的实验追踪目录约定——回答任务书"轻量实验追踪、不引数据库服务可借什么"这一问
- 挖什么:
  - 磁盘布局约定(文档 how-it-works + `src/dvclive/live.py`/`serialize.py`):`metrics.json`(最新摘要,可覆写)与 `plots/metrics/*.tsv`(append-only 步进序列)**分离**,加 `params.yaml`(本次运行参数快照)与生成式 `report.md`——对应到我们:`data/processed/versions/` 快照可补一份 run 级 `params.json`(founder/funnel 配置指纹),retro 的历史校准指标按 run append 成 tsv/jsonl 序列,`stats.py` 的 `format_report` 已经是 report.md 的雏形
  - `Live` 类的 API 极简面(`log_metric/log_param/next_step/make_report`)——如果未来给 ledger 加写入门面,这是被验证过的最小 API 形状
- SKIP 什么: 与 DVC/Git 实验管理的全部集成(`dvc.yaml` pipeline、`.dvc` artifact 文件、exp 分支魔法);各 ML 框架 callback(keras/lightning/hf);**不要 pip install**——dvclive 3.x 会把重量级 dvc 本体拖进依赖树
- 坑: 文档把 standalone 用法讲得含糊,实际依赖链偏重(拖 dvc/pandas 系),"轻量"只体现在磁盘产物而非安装体积;报告功能部分绑定 DVC Studio 云服务(忽略即可)
- recommendation: concepts-borrow
- 理由: 与本仓"每段落盘工件 + jsonl ledger"哲学同构的、被生产验证过的文件布局先例,借布局零成本
- 与硬约束的冲突: 依赖重(拖 dvc)→ 裁剪方式:只借目录约定和 API 形状,一行代码都不引

## 评估过但不推荐(skip 清单,防重爬)

- properscoring(github.com/properscoring/properscoring)— skip:Apache-2.0 但 2023-03 起停更;二元 Brier 公式只有一行、自己写更省,库的真正资产 `crps_ensemble`/`threshold_brier_score` 要等我们有分布式/集合预测才用得上,届时再回来挖 `properscoring/_brier.py`、`_crps.py`
- scoringrules(github.com/frazane/scoringrules)— skip:properscoring 的活跃继任者(Apache-2.0,2026-06 仍在推),但同理——proper scoring 公式书,当前点预测场景用不上;未来做概率化预测时优先于 properscoring 参考
- pybroker(github.com/edtechre/pybroker)— skip(仅概念):**Apache-2.0 + Commons Clause,禁商用,代码一行不能抄**;值得借的思想是 walkforward 评估 + bootstrap 置信区间型指标(样本少→区间宽→自然拒绝),bootstrap 是教科书算法可从零手写进 `calibrate.py`
- MAPIE(github.com/scikit-learn-contrib/MAPIE)— skip(仅概念):BSD-3、1.5k stars、活跃,但整库长在 sklearn 上;真正要借的是 split conformal 的最小样本数学(覆盖 1−α 需 n ≥ 1/α − 1)作为 `insufficient_data` 门槛的理论化升级,这一页论文级知识不需要碰它的代码
- mlflow(github.com/mlflow/mlflow)— skip:任务书预判正确——tracking server + 数据库后端 + artifact store,违反"不引数据库服务";可借的只有"每 run 一目录、params/metrics/tags 三分类"心智模型,dvclive 条目已覆盖同一概念的更轻版本
- aim(github.com/aimhubio/aim)— skip:Apache-2.0 但内嵌 RocksDB 存储 + web server 进程,"轻量"只是相对 mlflow,仍违反文件即真相
- trackio(github.com/gradio-app/trackio)— skip:MIT、HF 出品、活跃(1.5k stars),local-first 哲学对味,但存储是 sqlite + 仪表盘绑 gradio,而我们已有 jsonl ledger + studio;仅可借"wandb 兼容极简 API"这一点,价值不足以立项
- fortuna(github.com/awslabs/fortuna)— skip:**已 archived**(2025-04),且 JAX/Flax 重型栈
- Metaculus/forecasting-tools(github.com/Metaculus/forecasting-tools)— skip(本 lane):MIT、活跃,但主体是 LLM 预测 bot 框架,归 L5/L6 的菜;retro 相关的只有其 Benchmarker 的"bot 分数 vs 社区基线"思路,已被 fatebook 的相对 Brier 覆盖
- sacred(IDSIA/sacred)— skip:实验追踪默认 MongoDB observer,维护基本停滞
- guildai(github.com/guildai/guildai)— skip:曾是最好的"纯文件系统实验追踪",但 2023 年起停更、公司熄火,不宜登记为长期参考源
- freqtrade(hyperopt/walk-forward 部分)— skip:GPL-3.0 传染,只能借概念;且本仓已内化"the freqtrade lesson"(因子单一真相源),无新增可挖点

## 本 lane 的搜索方法沉淀

- 最高效入口:**GitHub API 直读 repo 元数据**(`api.github.com/repos/<org>/<repo>`)一次拿全 stars/license/pushed_at/archived,比搜索引擎快且准——archived 状态(fortuna)和真实 license(pybroker 的 Commons Clause 在 GitHub UI 只显示 "Other")都靠它/LICENSE 原文抓出来,**凡 license 显示 "Other" 必须去读 LICENSE 原文**,这是本次最大的避坑
- 好用检索词:"prediction tracking Brier score open source"(直达 fatebook)、"calibration metrics recalibration github"(直达 uncertainty-toolbox)、"<known-lib> alternative/lightweight"(properscoring→scoringrules 这条继任线就是这么找到的)
- 对 web app 型项目(fatebook),`api.github.com/repos/<r>/git/trees/main?recursive=1` 列树 + `raw.githubusercontent.com` 读单文件,能在不 clone 的前提下精确定位算法文件(`lib/_scoring.ts`);GitHub code search 网页版未登录不可用,是死胡同
- 死胡同:泛搜 "experiment tracking lightweight" 全是 mlflow/wandb 生态营销文;"decision journal open source" 几乎无代码级结果(该需求被 forecasting 社区的 prediction journal 品类吸收,fatebook 即代表)
- 未来 miner 起步建议:盯 fatebook `lib/_scoring.ts` 与 uncertainty-toolbox `metrics_calibration.py` 两个文件的 commit 历史即可覆盖本 lane 80% 的上游演化
