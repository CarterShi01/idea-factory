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

- [ ] **① Dify 实例可用**:开 `http://127.0.0.1:8080/install` 建管理员账号 → 在「设置→模型供应商」配好模型后端(创始人定的 claude -p custom provider)。*(前置:Dify 已部署在北京机并常驻,见 §3。)*
- [ ] **② 建两条 workflow**(照 `design/dify-integration.md` §3 迁移地图):
  - `idea-gen`:单 LLM 节点,system = `config/llm/generate.json` 的 system,user 透传(source/fusion 分支由 idea-factory 代码侧已选好再送),输出 `result`。
  - `idea-judge`:**两段链**(critique 节点 ← `config/llm/critique.json` → judge 节点 ← `config/llm/judge.json`),End 出终评 JSON。
  - **Start/End 变量必须对上契约**:输入 `system`/`user`/可选 `schema`,输出 `result`。
- [ ] **③ Export DSL → git**:每条流应用菜单 `Export DSL` → 落 `dify/flows/idea-gen.yml` / `idea-judge.yml`,提交。*(这是 GitOps 真相源。)*
- [ ] **④ 拿 key + 跑端到端**:每条流「API 访问」拿 App API Key → 设 `IDEA_DIFY_GENERATE_API_KEY` / `IDEA_DIFY_JUDGE_API_KEY` → `PYTHONPATH=src python3 -m idea_gen --gen-backend dify --top-n 15` 跑通,对比 `--gen-backend router` 输出是否对齐契约。
- [ ] **⑤ 拍 prompt 双份漂移决策**(重要):prompt 现在会同时在 `config/llm/*.json`(给 router/rule)和 Dify 流(给 dify)。**建议收敛到 Dify 单一 LLM 路径**:router 降为"Dify 挂了的离线 fallback",prompt 真相源 = Dify 导出的 DSL;`config/llm` 只留 schema + 非 prompt 配置。否则两份会漂(违 idea-factory "无漂移"气质)。详见 `design/dify-integration.md` §5。
- [ ] **⑥ import_flows.py 接进 deploy/CI**:部署时跑 `python3 dify/import_flows.py` 把 git 的 DSL 导回 Dify 实例(漂移即红),闭合 GitOps。
- [ ] **⑦(基建,非 idea-factory 代码,但要有人做)**:北京 Dify 公网暴露 = host nginx 加 dify 子域名反代 `127.0.0.1:8080` + TLS + 限速/API-key 配额(**别在 Lighthouse 直开 8080**);OC 侧 socat+防火墙持久化。详见 OC repo `docs/dify-deploy-runbook.md` / `docs/core-to-beijing-connectivity-runbook.md`。

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
