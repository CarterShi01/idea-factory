# reference/ — 开源参考源（只挖不跑）

> idea-factory 的**第三类外部代码桶**，机制移植自 one-creator 的 reference-miner
> （`team/reference/` 形制）：这里的项目是**被读、被挖的知识源**，永不运行、永不
> 成为依赖。目标：持续从开源生态吸取经验，优化八段漏斗的各个模块。

## 三件套

| 件 | 是什么 |
|---|---|
| [`sources.yaml`](sources.yaml) | ★注册表（唯一真相源）：每源 = id/repository/ref(钉 commit)/license/lanes/mined_for/status/mirror。由 `tests/test_reference_registry.py` 钉成 CI 规则。 |
| [`sync-source.sh`](sync-source.sh) | 镜像管理：`--add <id>` 首次登记镜像（git submodule + 钉 commit + 回写 ref）；`<id>`/`--all` 刷上游 + 回写。**上游 diff 不自动跟随**——变更经挖矿流程人审后才吸收。 |
| [`miners/<id>.md`](miners/) | ★per-source 挖矿沉淀（复利所在）：这个源的搜索方法 + 融合方法 + 历次决策/坑。骨架见 [`miner-template.md`](miner-template.md)；挖矿动作由 `/mine-reference <id>` skill 驱动。 |

调研底稿：`docs/research/reference-scan/`（00-brief 任务书 · L1–L10 lane 报告 ·
00-summary 汇合）。**skip/reject 负面清单住 00-summary §3**（防重爬，与推荐清单
同等重要）；重爬前先查那里。

## "面"（mined_for 落哪，决定闭合方式）

`lanes` = 产出落进哪个模块：八段(`recall/triage/generate/rank/enrich/diligence/
portfolio/retro`) + 两横切(`llm-infra`=runtime/llm 相关、`observability`=ledger/
studio 相关)。一源可多 lane。

`mined_for` 两面（判据：产出是数据还是机器代码）：

- **`d` 数据面**：prompt 文本、JSON schema、字段规范、默认参数、配置样板 →
  落 `config/`、`data/raw/fixtures/` 字段规范、`dify/flows`(注意镜像不变式)。
  **有门 promote**：miner 出候选 + provenance，创始人点头才进仓。
- **`m` 机制面**：算法、流程范式、纯函数、工程纪律 → **只提案**：miner 写清
  "建议怎么改 + 引用源文件"，创始人批准后才动 `src/idea_factory/`。

## 铁律

1. **只挖不跑**：不运行任何镜像内代码、不装其依赖；要"跑"某个东西 = 它不属于
   这个桶（走依赖申请，创始人批准）。
2. **引用不吞并**：产出落 idea-factory 自己的树；绝不回写镜像内部。
3. **promote 永远 HITL、一次一条**：抄任何代码（哪怕 60 行纯函数）进 `src/`
   都需创始人点头（CLAUDE.md 硬规则的自然延伸）。
4. **provenance 可溯**：凡从源里抄/改写的产物，头部注释
   `source: <id>@<sha>:<path>`（prompt/config 用 `_source` 字段）。
5. **license 纪律**：`mirror: false` 的源（AGPL/NC/RAIL 等，见 sources.yaml
   注释）**禁止镜像代码**，只读其设计文档/论文/公式，重新表述后自写实现，
   不做逐行改写；GitHub license 显示 "Other" 的必须人工读 LICENSE 原文。
6. **不自动跟随上游**：`sync-source.sh` 刷新只更新镜像与 ref；上游变化要经
   `/mine-reference <id>` 重新评估 + 人审，才 re-promote。

## 加一个新源 = 三步

```bash
# ① sources.yaml 注册一行(lanes/mined_for/status/license 必填;先别填 ref)
# ② 建镜像(自动钉当前 commit 并回写 ref;mirror:false 的源跳过本步)
reference/sync-source.sh --add <id>
# ③ 初始化挖矿沉淀文档(照模板)
cp reference/miner-template.md reference/miners/<id>.md  # 然后填"源速览/搜索方法"两节
```

评估过但不采纳的源：**不进 sources.yaml**，一句话理由记进
`docs/research/reference-scan/00-summary.md` §3（防重爬）。

## 放置判据（对齐 CLAUDE.md 的桶）

```
这个外部项目我们要…
├─ 运行/依赖它            → pyproject 依赖(需创始人批准;当前 stdlib-only)
├─ 只挖它的内容/模式       → reference/(本桶)
└─ 已评估不要             → 00-summary §3 负面清单(一句话理由)
```
