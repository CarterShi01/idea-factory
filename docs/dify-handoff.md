# Dify 接入 — 交接与待办(在 idea-factory 这里续上）

> 给**将来在 idea-factory 续这件事的人/会话**:这是当前进度 + 下一步 + 背景。冷启动打开这一篇就能接上。
> 深一层看 [`design/dify-integration.md`](design/dify-integration.md)(架构 + 迁移地图)、[`design/llm-abstraction.md`](design/llm-abstraction.md)(LLM 后端抽象)、[`../dify/flows/README.md`](../dify/flows/README.md)(流 I/O 契约)。

---

## 1. 背景速读(30 秒)

idea-factory 有**两个 LLM 步骤**:生成(`idea_gen.generate`)和评判(`idea_eval` 的 critique+judge)。
我们决定:**把这两步的 prompt 流搬到 Dify**(低代码可视化编排 prompt),`idea-factory` 经一个后端调它;
**`idea_core` 因子契约永远留 Python(不进 Dify),不许漂移。**

- **为什么 Dify**:拖拽改 prompt 流、流可 publish 成 MCP/HTTP、低代码迭代。Dify 当**叶子工具**,不当编排器。
- **真相源**:流定义(DSL YAML)进 git `dify/flows/`,Dify 是编辑器+运行时(GitOps,Dify 实例可从 git 重建)。
- **已经做完的**(分支已并 master):
  - `idea_core.llm.DifyBackend` + `get_backend("dify")` + 两 pipeline 接线 + CLI `--gen-backend/--judge-backend dify`(4 单测,全量 117 绿)。
  - `dify/flows/README.md`(契约)、`dify/import_flows.py`(CI 导回)、`docs/design/dify-integration.md`(设计+迁移地图)。
- **还没做的**:**Dify 里那两条流本身没建**(`dify/flows/*.yml` 还不存在)——这是下面待办的核心。

> ⚠️ idea-factory 有条硬约束(见 `design/llm-abstraction.md`):**不程序化调 Claude Code**。DifyBackend 调的是 Dify 的 HTTP endpoint(不是直接调 CC),模型选择是 Dify 那层的事,这侧保持干净。

---

## 2. 待办清单(按顺序,带"为什么")

- [ ] **① Dify 实例可用 + 接 claude -p 模型**:开 `http://127.0.0.1:8080/install` 建管理员账号 → 配模型后端(claude -p)。
  - ⚠️ **当前状态**:跑的是 **stock 官方镜像**(`langgenius/dify-*:1.14.2`),fork(`CarterShi01/dify`)**未做任何 claude -p 改动**。
  - ⚠️ **别 fork 核心源码**:compose 拉发布镜像、不 build 源码,改 `api/` 不生效(除非自建镜像,每次升级都要重 fork+rebuild,最重)。
  - **推荐 (a)**:起一个**包 claude -p 的 OpenAI 兼容 shim** → Dify「模型供应商 → OpenAI-API-compatible」填 shim URL(纯运行时配置,不 fork、不 rebuild、扛升级)。
  - 备选 (b):写 Dify 1.x **model-provider 插件**(正规扩展)。*(前置:Dify 已部署在北京机并常驻,见 §3。)*
- [ ] **② 建两条 workflow**(照 `design/dify-integration.md` §3 迁移地图):
  - `idea-gen`:单 LLM 节点,system = `config/llm/generate.json` 的 system,user 透传(source/fusion 分支由 idea-factory 代码侧已选好再送),输出 `result`。
  - `idea-judge`:**两段链**(critique 节点 ← `config/llm/critique.json` → judge 节点 ← `config/llm/judge.json`),End 出终评 JSON。
  - **Start/End 变量必须对上契约**:输入 `system`/`user`/可选 `schema`,输出 `result`。
- [ ] **③ Export DSL → git**:每条流应用菜单 `Export DSL` → 落 `dify/flows/idea-gen.yml` / `idea-judge.yml`,提交。*(这是 GitOps 真相源。)*
- [ ] **④ 拿 key + 跑端到端**:每条流「API 访问」拿 App API Key → 设 `IDEA_DIFY_GENERATE_API_KEY` / `IDEA_DIFY_JUDGE_API_KEY` → `PYTHONPATH=src python3 -m idea_gen --gen-backend dify --top-n 15` 跑通,对比 `--gen-backend router` 输出是否对齐契约。
- [x] **⑤ prompt 双份漂移决策 —— 已拍(2026-06-27,创始人)**:**收敛到 Dify 单一 LLM 路径**。一旦 Dify 上线,prompt 真相源 = Dify 导出的 DSL(进 git `dify/flows/`);`config/llm/*.json` 只留 `schema` + 非 prompt 配置(`step`/`temperature`/`batch_size`/`source_guidance`/`fusion`);router 降为"Dify 挂了的离线 fallback"。
  - ⚠️ **时序守卫(别提前抠 prompt)**:`config/llm/*.json` 的 `system`/`user_template` **要等 ④ 端到端跑通、确认 Dify 输出对齐契约后才删**。Dify 流是替代品,替代品没绿之前删 prompt = 砸掉当前唯一能跑的 router 路径。在此之前 `config/llm` 保持原样。
  - 落码动作(④ 绿之后):① 从 `generate/critique/judge/persona_sim.json` 移除 `system` + `user_template`(留 `schema` 等);② `idea_core.llm.load_config` / `build_request` 改为 prompt 缺失时不再从 config 取(走 Dify),router 走离线 fallback 的 prompt 来源单列;③ 更新对应单测。
  - 细节见 `design/dify-integration.md` §5.1(已标决策)。
- [ ] **⑥ import_flows.py 接进 deploy/CI**:部署时跑 `python3 dify/import_flows.py` 把 git 的 DSL 导回 Dify 实例(漂移即红),闭合 GitOps。
- [ ] **⑦(基建,非 idea-factory 代码,但要有人做)**:北京 Dify 公网暴露 = host nginx 加 dify 子域名反代 `127.0.0.1:8080` + TLS + 限速/API-key 配额(**别在 Lighthouse 直开 8080**);OC 侧 socat+防火墙持久化。详见 OC repo `docs/dify-deploy-runbook.md` / `docs/core-to-beijing-connectivity-runbook.md`。
  - 🔒 **公网已暴露 → 先做安全硬化再推进**:照 [`dify-public-hardening.md`](dify-public-hardening.md) 走(确认 `/install` 已认领、nginx 把后台锁 IP 白名单/basic-auth、TLS、限速/配额、暴露区隔离 + 验证 playbook)。**§8 全绿 = 安全**,之后再回 ②–④ 建流。动作 = 改运行栈/凭证(7 硬门),创始人/devops 执行。

---

## 3. 环境速查(北京 Dify)

| 项 | 值 |
|---|---|
| 机器 | 北京暴露机 `VM-0-15-ubuntu`,腾讯 Lighthouse,公网 `211.159.154.240`(**公网产品实例,OC 核心运行时不调它**)|
| Dify 部署 | `~/dify`(fork `CarterShi01/dify`),docker compose,**12 服务常驻**,向量库 **pgvector** |
| 本地端口 | **`127.0.0.1:8080`**(host 80/443 被另一个 nginx 占,故避开);idea-factory 同机走本地调 |
| 国内坑 | 装 docker 走阿里云 apt;镜像加速器配多 fallback(daocloud/1ms/tencent)。已踩平,见 OC `docs/dify-deploy-runbook.md` |

**DifyBackend 环境变量**(全表见 `dify/flows/README.md`):
```bash
IDEA_DIFY_BASE_URL=http://127.0.0.1:8080/v1   # 默认就是这
IDEA_DIFY_GENERATE_API_KEY=app-xxxx           # Dify「API 访问」拿
IDEA_DIFY_JUDGE_API_KEY=app-yyyy
# 可选:IDEA_DIFY_OUTPUT_KEY(默认 result)、IDEA_DIFY_USER、IDEA_DIFY_MIN_INTERVAL
```

---

## 4. 一句话

**骨架和文档都铺好了,缺的是"在 Dify 里把两条流画出来 + 导出 DSL + 设 key"。** 照 §2 顺序走,从 ① 到 ④ 就能端到端跑通 `--gen-backend dify`;⑤ 是开发前要拍的设计决策;⑥⑦ 是闭环和基建。

---

## ✅ 迁移完成实录(2026-06-27)

**端到端跑通**:`idea-gen --gen-backend dify`(14 信号→44 候选,真 LLM)+ `idea-eval --judge-backend dify`(44→20 review/24 killed,critique+judge 两流)。

**实际配置**:
- **Dify 实例**:北京 `di.enjoyapier.cloud`(公网 + IP 白名单,见 `dify-public-deploy-di.md`)。idea-factory 从核心机调,`IDEA_DIFY_BASE_URL=https://di.enjoyapier.cloud/v1`(核心机在白名单内)。
- **① 模型**:装 `langgenius/openai_api_compatible` 插件(marketplace) → 加模型 **`hy3-preview`**(LKEAP,`https://api.lkeap.cloud.tencent.com/plan/v3`,mode chat,ctx 65536),provider `langgenius/openai_api_compatible/openai_api_compatible`。
- **② 三条流**(瘦穿透:Start[system,user,schema]→LLM→End[result],温度各异):
  | step | app_id | 温度 | key 环境变量 |
  |---|---|---|---|
  | generate | 72a5aae9-f606-469d-b70b-f3c4a6bbb5d1 | 0.9 | `IDEA_DIFY_GENERATE_API_KEY` |
  | critique | a3323596-6380-48ff-93c2-a293e6713940 | 0.5 | `IDEA_DIFY_CRITIQUE_API_KEY` |
  | judge | 129a85df-8c55-4d92-89d2-14e3f8bdc7ba | 0.1 | `IDEA_DIFY_JUDGE_API_KEY` |
- **③ DSL**:`dify/flows/{idea-gen,idea-critique,idea-judge}.yml`(Dify 导出,git 真相源)。
- **④ key**:三个 App key 写在 idea-factory `.env`(gitignored)。

**踩的坑(给后人)**:
1. **LKEAP key**:`.env` 原本的 `sk-tp-NxQ...` 是 **cli-proxy-api 的客户端 key**,直连 LKEAP 公网 **401**。真 key 在 one-creator `external/router/cli-proxy-api/config.yaml` 的 `api-key-entries`(`sk-tp-0jf...`)。模型 ID = `hy3-preview`(在代理里别名 `tc-code`)。
2. **Dify 1.x 是插件化**:模型供应商也要先装插件;装插件时 `uv sync` 在国内会**死锁**——根因:daemon 用 `uv -v` 跑,verbose 输出塞满管道、daemon 不读 → uv 写阻塞。修法:给 `/usr/local/bin/uv` 套壳把输出排到文件(`exec uv.real "$@" >/tmp/uv-wrap.log 2>&1`),清 venv 重装即过(deps 走 `PIP_MIRROR_URL` 清华镜像 OK,pypi.org 被墙)。
3. **加模型只能 UI**:console API `POST .../model-providers/<prov>/models` 返回 `{"result":"success"}` 但**不持久化**(cc_status 仍 no-configure);UI 添加才真正存上。
4. **prompt 仍在 idea-factory 侧**(config/llm/*.json),流是瘦穿透 —— 符合 ⑤ 时序守卫(e2e 绿之前不抠 config)。⑤ 收敛到 Dify(把 prompt 搬进流、router 降 fallback)是**后续**可做项。
