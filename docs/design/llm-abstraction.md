# LLM 调用层通用抽象设计

> 面向 idea-factory 的两个需 LLM 步骤：**(A) idea 生成的 LLM backend**（`idea_gen.generate`）和 **(B) idea 评估的 LLM-as-judge**（`idea_eval`）。
> 目标：在**省 token** 的前提下，让这两步既能现在用腾讯 LLM 自动跑，又能在未来无缝切换到"人手动触发 Claude Code (CC) 当执行的手"。
> 本设计大量借鉴同级项目 **one-creator** 的做法（见文末"来自 one-creator 的事实依据"）。

---

## 0. 一句话结论

把每个 LLM 步骤抽象成一个**纯函数**：`一份提前备好的「请求包」文件 → 一份「响应包」文件`。
谁来填响应，由可插拔的 **Backend** 决定（腾讯 router / CC 当手 / mock）。
**请求包/响应包的契约不变**，所以"现在自动跑"和"将来 CC 手动跑"是同一套代码、零重写。

> ### ⛔ 硬约束（2026-06-15 起）
> **绝不允许任何程序化调用 Claude Code**（不准 headless `claude -p`、不准 SDK、不准 bridge/dispatcher 派发）。只有**人在 CC 终端手动交互**才走 Max 池计费。
> 因此本设计里：
> - 需要**自动化**的 LLM 步 → 只能走 **`RouterBackend`（腾讯 API，根本不是 CC）**。
> - 需要**走 CC / Max 池**的步 → 只能走 **`CCHandoffBackend`**：程序只写请求包文件并停下，**由人手动开 CC 处理整批**、写回响应文件，程序再读回续跑。**程序永不调起 CC。**
> - 无 LLM 的数据准备步走 cron 跑 `idea-gen`（纯 Python，零 token，也不碰 CC）。

---

## 1. 设计原则（从 one-creator 提炼）

| 原则 | 含义 | 在本设计里的落地 |
|---|---|---|
| **切两类，不切碎** | 把工作分成「无 LLM 的数据准备步（零 token）」和「需 LLM 的思考步」。思考步**批处理**，一次调用处理 N 条，绝不每条一调。 | DAG 每个 stage 标 `needs_llm`；无 LLM 步走 cron 零 token；LLM 步把整批打成**一个请求包** |
| **只对 Top-K 跑 LLM** | 先用硬规则（因子/kill-gate）把明显的废案砍掉，LLM 只评幸存者。 | eval：先跑零 token 的 `kill-gate` → 只把 survivors 交给 judge(B) |
| **默认走便宜引擎** | 思考默认走腾讯 LKEAP，绝不误触贵的计费池。 | `RouterBackend` 默认 `tc-code`；提供"引擎守卫"拒绝贵模型 |
| **结构化输出约束** | prompt 强制只输出 JSON，省掉解释性 token + 免解析。 | `LLMRequest.schema` + 容错 `extract_json` |
| **CC 只能手动交互，禁止程序调用** | （硬约束，2026-06-15 起）只有人在 CC 终端里手动交互才走 Max 池计费；任何程序化调用（含 headless `claude -p`、SDK、bridge 派发）一律禁止。 | `CCHandoffBackend` **永不调起 CC**，只产出请求包文件、停下；由人手动开 CC 跑一次、写回响应文件 |
| **数据提前备好** | 进入 LLM 步之前，所有上下文已落盘成自洽的请求包，人/CC 不用再东拼西凑。 | 请求包 `*.request.jsonl` 是自包含的 |

---

## 2. 核心抽象（三层）

```
       ┌─────────────────────────────────────────────────────────┐
  L3   │  Prompt/Schema 配置（config/llm/*.json，skill 可引用）     │  ← 改行为不改代码
       └─────────────────────────────────────────────────────────┘
                              │ 渲染
       ┌─────────────────────────────────────────────────────────┐
  L2   │  批请求包  list[LLMRequest]  ⇄  list[LLMResponse]          │  ← 不变的契约（兼容性铰链）
       └─────────────────────────────────────────────────────────┘
                              │ 谁来填
       ┌──────────────┬───────────────┬──────────────────────────┐
  L1   │ RouterBackend│ CCHandoffBack │ MockBackend / RuleBackend │  ← 可插拔后端
       │ (腾讯,自动)   │ (CC当手,人触发)│ (离线/测试/stage-0)        │
       └──────────────┴───────────────┴──────────────────────────┘
```

### L2 —— 不变的契约（最重要）

```python
@dataclass
class LLMRequest:
    id: str                 # 关联回某条 idea/candidate，用于把响应对回去
    system: str             # system prompt（来自 L3 配置）
    user: str               # 已渲染好的用户内容（含全部上下文，自包含）
    schema: dict | None     # 可选：响应必须满足的 JSON schema
    temperature: float = 0.2
    model: str | None = None
    meta: dict = {}         # 透传元数据（如 batch 序号）

@dataclass
class LLMResponse:
    id: str                 # 对回 LLMRequest.id
    text: str = ""          # 原始文本
    data: dict | None = None# 解析出的 JSON（若有 schema）
    ok: bool = True
    error: str = ""
```

```python
class LLMBackend(Protocol):
    name: str
    def complete(self, requests: list[LLMRequest]) -> list[LLMResponse]: ...
```

**接口是批优先的**（入参就是 `list`）。这从类型上逼着调用方"凑齐一批再调"，杜绝"每条一调"的碎切。

### L1 —— 三个后端

| 后端 | 何时用 | 行为 | token |
|---|---|---|---|
| **`RouterBackend`** | 现在 / 自动跑 | 直连腾讯 LKEAP（经 one-creator 的 router 或直连端点），OpenAI 兼容 | 腾讯计费（便宜） |
| **`CCHandoffBackend`** | 未来 / token 上量后 | **不调任何 API**；把整批请求落成 `*.request.jsonl`，抛 `PendingHandoff`；人在 CC 里跑一次 skill 填出 `*.response.jsonl`，pipeline 重跑即续上 | 走你 CC 订阅，按需、人控 |
| **`MockBackend` / `RuleBackend`** | stage-0 / 测试 / 离线 demo | 确定性本地产出，无网络 | 0 |

### L3 —— 配置驱动（skill agent config）

prompt、JSON schema、温度、批大小、模型，全部放 `config/llm/<step>.json`，代码只负责"渲染 + 调后端"。改行为 = 改配置，不动代码。这一层同时可被 `.claude/skills/` 下的 skill 引用，做到"agent config 驱动"。

```jsonc
// config/llm/judge.json
{
  "step": "judge",
  "model": "tc-code",
  "temperature": 0.1,
  "batch_size": 20,           // 一个请求包最多塞多少条
  "system": "你是冷酷的早期创业评审……只输出 JSON。",
  "schema": { "type": "object", "properties": { "verdict": {...}, "score": {...}, "kill_reasons": {...} } }
}
```

---

## 3. 两种执行模式（共享同一契约 = 兼容性铰链）

### 模式 1：自动模式（现在，调试期）
```
idea-gen --backend router   # generate(A) 直接调腾讯
idea-eval --backend router  # judge(B) 直接调腾讯
```
`RouterBackend.complete()` 内部 for-loop（或一次 mega-prompt）打腾讯，立即拿到响应。无人值守，适合 stage-1 调试。

### 模式 2：CC 当手模式（未来，省 token）
LLM 步**不连任何 API**，分两段：

```
# 第 1 段：pipeline 跑到 LLM 步，产出请求包后“暂停”
idea-eval --backend cc
  → 写出 data/llm_jobs/judge-2026-06-13.request.jsonl  （40 条 survivors 全在里面，自包含）
  → 抛 PendingHandoff，pipeline 停在这里

# 第 2 段：人开一次 CC，跑一个 skill（一次触点处理整批）
$ cd idea-factory && claude
  /run-llm-batch judge-2026-06-13      # skill 读 request.jsonl，用 CC 这只“手”思考，写 response.jsonl

# 第 3 段：pipeline 重跑，自动续上
idea-eval --backend cc                 # 检测到 response.jsonl 存在 → 读回 → 继续 memos
```

**关键**：两种模式下 `*.request.jsonl` / `*.response.jsonl` 的 schema 完全一致。
- 现在写 `RouterBackend`，将来加 `CCHandoffBackend`，**generate/eval 的业务代码一行不改**。
- 一个请求包 = 一整批（40 条）= 人**一次** CC 触点，不是 40 次。这就是你要的"不要老让人分段执行"。

> 省 token 纪律照搬 one-creator 的 `cc.sh`：headless CC 默认 lock，跑批前 `cc.sh on`、跑完 `cc.sh off`。

---

## 4. 插进 DAG 的什么位置

```
idea_gen:
  collect ─ normalize ─ dedup ─ generate ─ score ─ rank ─ export        ──ideas.json──▶
  [no_llm] [no_llm]   [no_llm]  ★A LLM    [no_llm] [no_llm][no_llm]

idea_eval:
  read ─ kill_gate ─ judge ─ memos
  [io]   [no_llm]    ★B LLM  [no_llm]
         │只对 Top-K│
         └ 砍掉废案 ┘
```

- **★A 生成**：`generate` 的 backend 从规则版换成 LLM 版（接口已为此预留：`generate(signals, backend=...)`）。LLM-A 做"发散过量生成 + Verbalized Sampling 多样性"。
- **★B 评审**：`kill_gate`（零 token 硬规则）先把 42 条砍成 ~Top-K，**只有 survivors 进 judge**。LLM-B 做多维评分 + 对抗式批判，吐结构化 JSON。
- 其余 stage 全是 `no_llm`，归 cron 零 token 跑（数据提前备好）。

**每个 stage 显式带 `needs_llm` 标志**，调度器据此决定：no_llm → cron `no_agent` shell；llm → 走 Backend。

---

## 5. MCP 外挂（可选，给交互式 CC 用）

把 generate/judge 包成一个小 **FastMCP server**（照抄 `brain-mcp/server.py` 骨架），暴露 `idea_generate(signal)` / `idea_judge(candidate)` 工具。
- 适用场景：你在 CC 里**交互式**地"再帮我评一下这条"。
- **但批处理不要走 MCP**——批处理用第 3 节的请求包文件更省、更可控。MCP 是"按需单发"，文件包是"批量离线"。两者并存，按场景选。

---

## 6. 腾讯 LLM 复用细节（初期）

直接复用 one-creator 的 `router_chat`（`brain-mcp/think_tools.py`），纯 stdlib urllib、OpenAI 兼容：

| 配置项（env） | 默认 | 说明 |
|---|---|---|
| `IDEA_LLM_BACKEND` | `mock` | `mock` / `router` / `cc` |
| `IDEA_LLM_BASE_URL` | 回退 `OPENAI_BASE_URL`，再回退 `http://cli-proxy-api:8317/v1` | **须含版本段**（`.../v1` 或 `.../plan/v3`），代码只追加 `/chat/completions` |
| `IDEA_LLM_API_KEY` | 回退 `OPENAI_API_KEY`，再回退 `local-router-key` | 真实 key **只放 env / gitignored，不进 git** |
| `IDEA_LLM_MODEL` | 回退 `OPENAI_MODEL`，再回退 `tc-code` | 经 router 用别名 `tc-code`；直连 LKEAP 用其真实模型名 |

`RouterBackend` 优先读 `IDEA_LLM_*`，未设则回退标准 `OPENAI_*`，所以环境里若已有 OpenAI 兼容端点（如腾讯 LKEAP）即开箱可用。

**安全纪律（照搬 one-creator）**：真实 provider key 只放一处且 gitignored；提供"引擎守卫"硬拒 Anthropic 端点/claude* 模型，保证省 token 步永远走腾讯。
**批处理注意**：腾讯 LKEAP 无原生 batch API，"批"靠在一个 prompt 里塞多条（一次评 N 条），由 `batch_size` 控制。

---

## 7. 分阶段落地路线

| 阶段 | 做什么 | backend | 触发 |
|---|---|---|---|
| **现在 (stage 0)** | 规则版 generate + 规则版 kill-gate（已完成） | `mock`/`rule` | 离线，零 token |
| **stage 1（调试）** | 落地 `idea_core/llm.py` 抽象；generate(A)/judge(B) 接 `RouterBackend` 连腾讯；prompt 进 `config/llm/*.json` | `router` | 自动（cron `no_agent` 备数据 + 一条命令跑 LLM 步） |
| **stage 2（省 token）** | 加 `CCHandoffBackend` + `/run-llm-batch` skill；token 上量后切到 CC 当手 | `cc` | 人手动一次性触发 CC |
| **stage 3（可选）** | generate/judge 暴露成 MCP，供交互式 CC 按需单发 | 任意 | 交互 |

**每跨一阶段，业务代码不重写**——只换 `--backend` 和配置。这正是本抽象的目的。

---

## 8. 代码骨架（已落地最小版见 `src/idea_core/llm.py`）

```python
# 选后端：一个工厂，读 env
backend = get_backend(os.environ.get("IDEA_LLM_BACKEND", "mock"))

# generate(A) 用法
reqs = [render_request("generate", signal) for signal in fresh]   # L3 配置渲染
resps = backend.complete(reqs)                                    # L2 契约 + L1 后端
candidates = [parse_candidates(r) for r in resps]

# judge(B) 用法（只对 survivors）
survivors = kill_gate(ideas)                # 零 token 先砍
reqs = [render_request("judge", s) for s in survivors]
resps = backend.complete(reqs)              # router 自动 / cc 产包待人填
verdicts = [r.data for r in resps]
```

---

## 来自 one-creator 的事实依据（subagent 调研）

- **腾讯客户端**：`brain-mcp/think_tools.py` 的 `router_chat()`（stdlib urllib，OpenAI 兼容）+ `_extract_json()` 容错解析 —— 直接可搬。
- **router 配置**：`external/router/cli-proxy-api/config.example.yaml`，端点 `https://api.lkeap.cloud.tencent.com/plan/v3`，别名 `tc-code`。
- **零 token 数据准备**：`hermes-home/cron/jobs.json` 已有 `idea-factory-daily`（`no_agent:true`）+ `scripts/idea_factory_daily.sh`。
- **CC 成本开关纪律**：`team/scripts/cc.sh`（默认 lock，跑批才 on，跑完 off）。
- **CC 当手的异步范式**：`brain-mcp/bridge.py`（非 LLM 占位进程撑开 run，人干完发 `signal` 收尾）—— 思想借鉴，初期不照搬其 Hermes 耦合。
- **省 token 流水线纪律**：`hermes-home/skills/research/idea-pipeline/SKILL.md`（"QuickFilter 硬规则不用 LLM；DeepAnalyze 只对 Top-K 跑"）—— 与本设计第 4 节一致。
- **MCP 骨架**：`brain-mcp/server.py`（FastMCP，stdio/HTTP）。
