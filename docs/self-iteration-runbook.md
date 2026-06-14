# 三轮自我迭代 Runbook（毒舌投资人 + 创始人画像）

目标：让 idea-factory 在「创始人就是执行者」的真实约束下，被一位**默认拒投的毒舌投资人**
连续撕三轮，每轮据批判收紧系统，直到产出的 idea 经得起 founder-fit 拷问。

> 纪律：**真·LLM 三轮由创始人在腾讯 (`router` / tc-code) 上跑**（CC 侧只做实现 + 离线
> pytest，绝不耗计量跑全流程）。本 runbook 给的是每轮要敲的命令 + 量化判读 + 收紧动作。

## 已就位的两件武器
- **创始人画像** `config/founder.json`：10 年程序员+PM / 6 万启动资金 / 安全云 B2B+中东
  硬件出海+医生 三类低成本人脉 / 内蒙古蒙语家人(小语种区域独占壁垒)。
  自动注入到 generate/critique/judge 三步的 system prompt（`idea_core.llm.build_request`），
  并折进 `distribution_fit` 因子的可触达词表。改画像即改全管线对 founder-fit 的判断。
- **毒舌投资人 critic** `config/llm/critique.json`：默认拒投，五类要害(伪痛点/创始人做不了/
  假市场/无护城河/时机错)，**强制至少一条 founder-fit(资金·渠道·能力)攻击**；评委(judge)
  必须在 `respond_to_critique` 里逐条回应，不能装没看见。

## 每轮命令（腾讯 router）
```bash
cd idea-factory
export IDEA_LLM_BACKEND=router            # 走腾讯 LKEAP，非 OAuth(封号红线)
# 生成≠评估用不同模型(反自我增强)：可选
# export IDEA_LLM_CRITIQUE_MODEL=...  export IDEA_LLM_JUDGE_MODEL=...

R=round1   # 每轮换 round2 / round3
OUT=data/processed/$R
mkdir -p $OUT

# 1) 生成（三源 + 融合 + 画像注入）
PYTHONPATH=src python3 -m idea_gen --gen-backend router --output-dir $OUT --top-n 15

# 2) 评估（毒舌 critic → 评委，都带画像）
PYTHONPATH=src python3 -m idea_eval --judge-backend router \
    --input $OUT/ideas.json --output-dir $OUT --top-n 15

# 3) 量化记分卡（对比上一轮是否真变好）
PYTHONPATH=src python3 scripts/round_report.py \
    --ideas $OUT/ideas.json --screened $OUT/screened.json --label $R --top-n 15
```

## 每轮判读（round_report 输出怎么看）
- **factor spread**：`build_cost` / `moat_signal` 的 `stdev` 必须 >0、`distinct` 多档——
  若又回到全 1.0 / 全 0.1 说明因子退化(投资人复评 #1)。
- **Non-Duplicate Ratio**：Top-15 应 ≥ ~0.8；若骤降说明近重又挤占头部(投资人复评 #3)。
- **三源融合候选**：digest 内应至少有 1-2 条 fusion(mission 护城河兑现)。
- **founder-fit 命中**：digest 里命中可触达渠道(安全云/中东/医疗/蒙语…)的条数——这是
  本次新增的核心指标，越高说明越贴合创始人真能落地的方向。
- **verdicts / kill-rate**：毒舌 critic 上线后 kill-rate 应明显高于旧版；活下来的(pursue)
  才是真经得起拷问的。

## 三轮收紧动作（据批判改什么）
- **Round 1（基线）**：先看毒舌 critic 把哪类 idea 成批杀掉。典型新症结：① 大量 idea
  「用不上创始人任何杠杆」(冷启动陌生市场) → 收紧 `generate.json` 引导，强调优先利用
  画像里的渠道/语言优势；② founder-fit 命中过低 → 调 `founder.json` 的 reach 关键词或
  在生成指引里点名「优先 安全云 B2B / 中东硬件出海 / 蒙语区域」。
- **Round 2**：看 judge 的 `respond_to_critique` 有没有真回应 founder-fit 攻击，还是空话
  搪塞 → 若搪塞，强化 `judge.json` 的 `reachable`/`solo_buildable` 校准(明确：6 万烧不起
  获客=reachable 低分；要团队=solo_buildable 低分)。把仍混进来的伪痛点/科幻市场记下，
  回流到 critique 的要害清单或 factors 的痛点门。
- **Round 3（收尾）**：此时存活的 idea 应同时满足「痛真 + 一人 6 万能做 + 有渠道拿到前 10
  个用户 + 有壁垒(最好沾蒙语/区域/独占集成)」。剩余 1-2 条致命系统性问题再补最后一刀；
  把每轮 `round_report` 记分卡贴进 `idea-factory-evolution/round{N}-critique.md` 留痕。

## 约束（不可破）
stdlib 为主、不引 embedding/向量库/Web UI/DB/框架；ideas.json/screened.json schema 兼容；
离线 rule 路径 + pytest 必须绿；因子两仓共用一套；演进不重写。
