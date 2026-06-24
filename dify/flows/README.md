# dify/flows — Dify prompt 流(git 真相源,GitOps)

> **这里是 idea-factory 的 LLM prompt 流的单一真相源。** Dify 当编辑器 + 运行时,**git 当真相源**。
> 不单独拆第三方 prompt registry —— 因为流的 I/O 必须和 `idea_core` 因子契约对齐,**必须和它一起版本化**
> (拆开 = 重造 `idea_core` 当初要消灭的漂移)。设计论证见 OC repo `docs/design/dify-integration.md`。

## 这个目录放什么

每个 `*.yml` = 一个 **Dify workflow app 导出的 DSL**(YAML)。当前规划两条流:

| 文件 | 对应步骤 | idea-factory 怎么用 |
|---|---|---|
| `idea-gen.yml` | 生成 + 打分(generate) | `idea-gen --gen-backend dify` |
| `idea-judge.yml` | 毒舌 critic + 评委(critique/judge) | `idea-eval --judge-backend dify` |

> ⚠️ 目前是**骨架**:`.yml` 还没产出 —— 等在 Dify 里把流画好、`Export DSL` 落到这里。

## 流的 I/O 契约(在 Dify 里画流时,Start/End 节点变量必须对上)

`idea_core.llm.DifyBackend` 按这个契约调流:

- **Start 节点输入**:文本变量 `system`、`user`(可选 `schema` = JSON schema 字符串)。
- **End 节点输出**:一个变量 `result`(文本;若需结构化,流内自己产 JSON 文本,idea-factory 侧按 `schema` 抽取)。
- **prompt 本体活在 Dify 流里**,idea-factory 只送 `system`/`user` 内容 + 可选 schema。

> 变量名可经环境变量覆盖(见下),但**默认就按这套**最省事。

## 工作循环(Dify 编辑 → git 真相 → CI 导回)

```
在 Dify UI 画/调流(人体工学)
  → 应用菜单 Export DSL
  → 把 .yml 提交进 dify/flows/(本目录,git 真相源,和 idea_core 同 PR 改)
  → CI / 部署脚本经 import_flows.py 把 DSL import 回 Dify 实例(漂移即红)
```

**真相源是 git,Dify 实例是可从 git 重建的部署目标**——不是反过来。

## 凭证不进 git(重要)

**Dify 导出的 DSL 不含工具节点的密钥**(API key 等)。所以:
- ✅ 流定义可以安全进 git,不会泄密。
- ⚠️ 导入实例后,需在 Dify 里**重新填工具/模型凭证**(或部署时注入),DSL 里没有。

## DifyBackend 的环境变量(`idea_core/llm.py`)

| env | 默认 | 说明 |
|---|---|---|
| `IDEA_DIFY_BASE_URL` | `http://127.0.0.1:8080/v1` | Dify API 根(北京机本地)|
| `IDEA_DIFY_<STEP>_API_KEY` | — | 每条流的 App API Key(Dify「API 访问」面板生成);`<STEP>`=`GENERATE`/`CRITIQUE`/`JUDGE` |
| `IDEA_DIFY_API_KEY` | — | 兜底 key(没分步 key 时用)|
| `IDEA_DIFY_OUTPUT_KEY` | `result` | End 节点输出变量名 |
| `IDEA_DIFY_USER` | `idea-factory` | Dify 调用方标识 |
| `IDEA_DIFY_MIN_INTERVAL` | `0.5` | 批内节流(小机器/单 worker)|

> `idea_core`(因子契约)仍是 Python 真相源,**不进 Dify**;Dify 只管 LLM 生成/评判那几步。
</content>
