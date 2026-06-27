# Dify 集成设计（idea-factory 侧）

> idea-factory 的两个 LLM 步骤（**生成 idea_gen.generate** / **评判 idea_eval 的 critique+judge**)可以走 **Dify 工作流**当后端。
> 本文自包含:**北京 Dify 部署事实 + 架构 + 把现有 prompt 迁进 Dify 的精确地图 + 开发循环**。
> 是 [`llm-abstraction.md`](llm-abstraction.md) 的延续——dify 是它第 4 个 Backend(router / cc / mock / **dify**)。
> 系统级取舍(为什么 Dify 当叶子、信任区隔离)在 one-creator repo `docs/design/dify-integration.md`;**本文只讲 idea-factory 这侧,够你在这里开发。**

---

## 0. 一句话

`idea_core`(因子契约)永远是 **Python 真相源,不进 Dify**;只有**两步 LLM 的 prompt 流**进 Dify;
`idea_core.llm.DifyBackend` 调 Dify 的 workflow endpoint;**流定义(DSL)的真相源在 git(`dify/flows/`),Dify 是编辑器+运行时**。

---

## 1. 现状:**已搭好后端骨架,prompt 流还没建**

| 件 | 状态 |
|---|---|
| `idea_core.llm.DifyBackend` + `get_backend("dify")` + 两 pipeline `_llm_backend` + CLI `--gen-backend/--judge-backend dify` | ✅ 已落(分支 `feat/dify-backend`,4 单测 + 全量 117 绿) |
| `dify/flows/README.md`(I/O 契约)+ `dify/import_flows.py`(CI 导回) | ✅ 已落 |
| **`dify/flows/idea-gen.yml` / `idea-judge.yml`(真正的流)** | ❌ **没建** —— 要你在 Dify 里画好 → Export DSL 落进来 |
| Dify 里的两条 workflow + 每条的 API key | ❌ 待你建 |

> 为什么 `.yml` 不是我生成的:Dify 流在**可视化编辑器**里建,DSL schema 复杂且版本相关,从命令行硬写不可靠也没法测导入。所以正确路径 = 你照下面**迁移地图**在 Dify 里重建。

---

## 2. 北京 Dify 部署事实(你开发时要知道的环境)

- **机器**:北京暴露机 `VM-0-15-ubuntu`(腾讯 Lighthouse,公网 `211.159.154.240`)。**这是公网产品实例(暴露区)**;OC 核心(新加坡)运行时**不调它**(no-straddle 隔离)。
- **Dify 跑在**:`~/dify`(fork `CarterShi01/dify`),docker compose,**12 服务常驻**,向量库 = **pgvector**(非 weaviate,省内存)。
- **本地端口**:Dify 对外 nginx 映射在 **`127.0.0.1:8080`**(host 的 80/443 被另一个 nginx 占了,故避开)。idea-factory 在**同机**跑,就走 `http://127.0.0.1:8080` 本地调,不经公网。
- **公网访问**(将来):由 host nginx 加 dify 子域名反代 `127.0.0.1:8080` + TLS;**别在 Lighthouse 直开 8080**。
- **国内网络坑**(已踩平,见 OC repo `docs/dify-deploy-runbook.md` 实战记录):装 docker 走阿里云 apt 源、镜像加速器配多个 fallback(daocloud/1ms/tencent)。
- **登录/管理**:Dify `/install` 建管理员;每条流在「API 访问」面板拿 App API Key。
- **模型后端**:Dify 内部用创始人配的 custom provider(claude -p)。⚠️ 注意 idea-factory 自己的硬约束(见 `llm-abstraction.md`:不程序化调 CC)——**DifyBackend 调的是 Dify 的 HTTP endpoint,不是直接调 CC**;模型选择是 Dify 那层的事,idea-factory 这侧保持干净。

---

## 3. 迁移地图:现有 prompt → Dify 流(照这个在 Dify 里重建)

**两个 Dify workflow app,I/O 契约统一**(`DifyBackend` 按此调):
- **Start 节点输入**:`system`(文本)、`user`(文本)、可选 `schema`(JSON schema 字符串)。
- **End 节点输出**:`result`(文本;若要结构化,流内产 JSON 文本,idea-factory 侧按 schema 抽取)。
- prompt 本体放进**流里的 LLM 节点**;idea-factory 只送 system/user 内容。

### 流 A:`idea-gen.yml`(生成)← `config/llm/generate.json`
- **system 提示词** = `generate.json` 的 `system`(Peter Thiel 式垄断生成器 + 三步从独占资源反推 + monopoly 三字段 + 硬禁止模板)。直接搬进 LLM 节点。
- **user** = idea-factory 渲染好 `user_template`(填了 `{title}/{pain_statement}/{category}/{source}/{source_guidance}`)后整段送进来。**注意**:`source_guidance`(按 external_event/brain_inbox/pain_persona 分支的文案)和 `fusion`(三源融合的另一套 system/user)目前由 **idea-factory 代码侧选好再送**——所以**流 A 收到的就是渲染完的最终 user**,流内不用再分支。最省事的迁法 = 流 A 只一个 LLM 节点(system 固定、user 透传)。
- **schema** = `generate.json` 的 `schema`(candidates 数组,每条 11 字段含 why_only_me/first_10_customers/copy_fails_because)。

### 流 B:`idea-judge.yml`(评判)← `config/llm/critique.json` + `judge.json`
这步是**两段链**(devil's advocate → judge),Dify 流里正好两个 LLM 节点串起来:
- **节点 1 critique** ← `critique.json` 的 system(毒舌投资人,默认拒投,5 类要害,≤40 字纪律)+ user_template。产出 objections/killer_objection/doomed_assumption。
- **节点 2 judge** ← `judge.json` 的 system(犀利评委,先 respond_to_critique 逐条回应,五维子分,score 校准)+ user_template(把节点 1 的 critique 填进 `{critique}`)。产出 verdict/score/scores/respond_to_critique/…
- 对应 idea-factory 侧:`--judge-backend dify` 时 step=critique / judge 各调一次(或你把两节点合进一条流,End 输出 judge 结果)。**推荐合成一条流**(Start 收 idea 字段 → critique 节点 → judge 节点 → End 出 judge JSON),idea-factory 一次调用拿终评。

> **prompt 现在还在 `config/llm/*.json`,版本控制着,不用"搬走"。** 迁移 = 把这些 system/user 内容在 Dify LLM 节点里重建。`config/llm/*.json` 仍是 **router/rule/mock 后端**的 prompt 源(见下"开放问题")。

---

## 4. 开发循环(GitOps:Dify 编辑 → git 真相 → 导回)

```
在 Dify UI 画/调流（http://127.0.0.1:8080，人体工学）
  → 应用菜单 Export DSL
  → 把 .yml 提交进 dify/flows/（git 真相源，和 idea_core 同 PR 改）
  → 部署/CI 跑 python3 dify/import_flows.py 把 DSL 导回 Dify 实例（漂移即红）
```

**跑通端到端**:
```bash
export IDEA_DIFY_BASE_URL=http://127.0.0.1:8080/v1
export IDEA_DIFY_GENERATE_API_KEY=app-xxxx    # Dify「API 访问」拿
export IDEA_DIFY_JUDGE_API_KEY=app-yyyy
PYTHONPATH=src python3 -m idea_gen --gen-backend dify --top-n 15
PYTHONPATH=src python3 -m idea_eval --judge-backend dify
```
环境变量全表见 [`../../dify/flows/README.md`](../../dify/flows/README.md)。

---

## 5. 开放问题 / 设计决策(开发前想清)

1. **prompt 双份漂移 —— 已决策(2026-06-27,创始人):收敛到 Dify 单一 LLM 路径。** 同一 prompt 现在会同时存在 `config/llm/generate.json`(给 router/rule)和 Dify 流(给 dify),两份会漂。定的方案:
   - **✅ 选定:收敛到 Dify 单一 LLM 路径**。一旦上 Dify,router 降级为"Dify 挂了的离线 fallback",prompt 真相源就是 Dify 流(导出的 DSL 在 git);`config/llm` 只留 schema + 非 prompt 配置。
   - ⚠️ **时序守卫**:此瘦身(从 `config/llm/*.json` 删 `system`/`user_template`)**必须在端到端 ④ 跑通、Dify 输出对齐契约之后**才做 —— 否则会在替代品(Dify 流)就绪前砸掉当前唯一能跑的 router 路径。在此之前 config/llm 保持原样。
   - ~~保 `config/llm` 为权威,Dify 流当投影(每次手动同步)~~——违 idea-factory 的"无漂移"气质,**未选**。
   - ~~两后端各管各的 prompt(接受双份)~~——仅短期 A/B 对比 router vs dify 用,**未选为长期态**。
2. **`idea_core` 不进 Dify**:因子契约(`idea_core/factors.py`、schema)是"不许漂移"的命门,永远 Python。Dify 流只产文本,结构化抽取/校验仍在 idea-factory 侧(`schema` + `extract_json`)。
3. **fallback 白捡**:`--gen-backend rule|mock` 仍在 → Dify 不可用时能退回离线,registry 派得专门做的缓存/fallback 你天生就有。

---

## 6. 关系到 one-creator(指针,不复述)

- 完整北京部署步骤 + 国内网络坑:OC repo `docs/dify-deploy-runbook.md`。
- 系统级取舍(Dify=叶子不当编排器 / no-straddle 双实例 / 连通避坑):OC repo `docs/design/dify-integration.md`、`docs/core-to-beijing-connectivity-runbook.md`。
- **但你在 idea-factory 这里开发,看本文 + `llm-abstraction.md` + `dify/flows/README.md` 三篇就够。**
