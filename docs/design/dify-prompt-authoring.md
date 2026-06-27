---
doc: design
title: "Dify 作为 prompt 的可视化编辑面(⑤ 收敛落地)"
date: 2026-06-27
related: [dify-integration.md, llm-abstraction.md, ../dify-handoff.md]
---

# Dify = prompt 的可视化编辑面(⑤)

> 目标(创始人):**以后所有"调 LLM + 定义 prompt 流程"的步骤都放 Dify,随时可视化调整;不靠手拖,由 OC 平台(这只手)经 console API 操控落地。**
> 本文是架构评审结论 + ⑤(把 prompt 从 `config/llm` 收敛进 Dify 流)的落地设计。

## 0. 能力前提(已验证)
OC 这只手可经 Dify console API **全程无人拖拽**地建/改/发布/导出流(浏览器会话 + X-CSRF-Token fetch,或 SSH)。循环:
```
我改 DSL(git 真相)──import/publish──▶ Dify 实例
       ▲                                  │
       └─ 你在 Dify UI 可视化微调 ─export─┘  (回写 git,防漂移)
```

## 1. 边界铁律(什么上 Dify,什么留 Python)
**Dify 只放 prompt(自然语言、常调、无硬契约)。** Python 永远留:
- `idea_core/factors.py`(打分,唯一真相源,**绝不漂移** —— freqtrade 教训)
- kill-gate(乘法下限)、排序(MMR/时间衰减)、去重
- JSON schema 抽取 + 校验(`extract_json`,idea_core 契约)

Dify 出**文本**;Python 抽取 + 校验 + 打分。破这条 = 回到 idea_core 要消灭的漂移。

## 2. 三个 LLM 点是否该上 Dify(评审结论)
| 点 | 上 Dify? | 说明 |
|---|---|---|
| generate | ✅ | prompt 最重(Verbalized Sampling/源差异化/founder),最该可视化 |
| critique | ✅(最受益) | 毒舌多角度,Dify 画布最适合编排成多节点(后续可拆) |
| judge | ✅ prompt;⚠️ **kill-gate 留 Python** | 评分 prompt 可调;裁决门是确定性逻辑,不进 Dify |
| persona_sim | 🔵 可选(现 static) | 同为 prompt 步,要一致性可一并上 |

**结论:三点都该上(都是 prompt 步)。** judge 划清"可调=评分prompt / 不可动=kill-gate"。

## 3. ⑤ 落地设计(精简方案,stdlib-only 友好)
### 3.1 prompt 的家 = Dify 流
- 每条流 LLM 节点的 **system 文本 = 该步的策略 prompt**(从 `config/llm/<step>.json` 的 `system` 搬入,嵌进流)。**这就是你在 Dify 里可视化编辑的地方。**
- user 文本 = `{{#start.user#}}`(idea-factory 渲染好的数据)。

### 3.2 founder 画像走数据(不写死进 Dify)
- `config/founder.json` 仍是 founder 真相源。`build_request` 把 founder block **拼进 user**(而非 system)——对 Dify(经 user 入流)和 router 都生效,改 founder.json 即刻反映,无需动 Dify。

### 3.3 config/llm 留作 stdlib 镜像(防漂移)
- idea-factory 是 **stdlib-only**(不能读 YAML),故 `config/llm/<step>.json` 的 `system` **保留**,作:① router/mock 离线 fallback 的 prompt 源;② Dify 嵌入策略的镜像。
- **不变式**:`config/llm/<step>.json.system` ≡ `dify/flows/<step>.yml` LLM 节点 system。靠 GitOps 同步(你在 Dify 改→我 export 回写 config/llm + yml)+ ⑥ CI 校验(不一致即红)。
- `user_template` / `schema` / `temperature` 仍留 config/llm(数据绑定 + 契约,小、属代码侧)。

### 3.4 后端行为
- **DifyBackend**:只送 `{user, schema}`(不再送 system —— 流自带策略;founder 已在 user 内)。
- **RouterBackend / Mock**:用 `LLMRequest.system`(= config 策略)+ `user`(= founder + 数据),与 Dify 路径同 prompt。

## 4. 取舍 / 后果
- **好**:prompt 在 Dify 可视化调(创始人目标达成);founder 仍数据驱动;router 离线仍可用;factors/gate 不漂。
- **代价**:策略 prompt 有两份表示(Dify 嵌入 + config/llm 镜像),靠同步 + CI 防漂移(stdlib-only 下的务实折中;若将来允许加 PyYAML 依赖,可让 idea-factory 直读 DSL,做到单一源)。
- **同模型**:本期三条流都用 `hy3-preview`(不按步换模型;按步选模型是后续优化)。

## 5. 落地步骤(本期)
1. `build_request`:founder block → 拼进 user(原拼进 system)。
2. `DifyBackend._run`:inputs 只送 `{user[, schema]}`。
3. `dify/flows/{idea-gen,idea-critique,idea-judge}.yml`:LLM system = 嵌入对应 `config/llm` 策略;Start 去掉 `system` 变量(留 `user`/`schema`);re-import + publish。
4. 测试:`pytest`(更新 build_request / DifyBackend 用例)+ e2e(`idea-gen --gen-backend dify` & `idea-eval --judge-backend dify`)绿。
5. 后续(非本期):⑥ CI 漂移校验、critique 拆多节点、按步选模型、persona_sim 上 Dify。
