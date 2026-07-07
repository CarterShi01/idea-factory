---
name: mine-reference
description: 对 reference/sources.yaml 里登记的一个开源参考源执行一轮挖矿——刷镜像、按 miners/<id>.md 的方法定位资产、产出"有门 promote 候选(数据面)/机制提案(机制面)"、把方法与坑追加进沉淀日志。Invoke as "/mine-reference <id>"(或不带 id 列出可挖源)。上游 sync 出现 diff、或某段要吸取开源经验时用。
---

# /mine-reference <id> — 对一个登记源执行一轮挖矿

## 你要做什么(流程)

1. **读三处上下文**(顺序固定):
   a. `reference/sources.yaml` 里 `<id>` 那条(lanes/mined_for/status/license/mirror/note);
   b. `reference/miners/<id>.md`(该源的搜索方法 + 融合方法 + 历次沉淀——**不存在则先
      `cp reference/miner-template.md reference/miners/<id>.md`,从 sources.yaml note 与
      调研底稿填好前两节**);
   c. 调研底稿 `docs/research/reference-scan/L*.md` 中该源小节("挖什么/SKIP/坑")。
2. **备镜像**:`reference/sync-source.sh <id>`(无镜像先 `--add <id>`)。
   - `mirror: false` 的源(AGPL/NC/RAIL):**跳过镜像**,只经 WebFetch 读其文档/论文/
     README/社区注解仓;绝不把其代码写进任何文件。
3. **挖**:按 miners/<id>.md 的搜索方法定位资产;逐面产出:
   - **数据面 d** → 写成 promote 候选:改写好的 prompt/schema/参数(中文化、字段对齐),
     放到目标位置的**草稿**(如 `config/llm/<step>.json` 的建议 diff 贴在产出报告里,
     不直接覆盖),头部带 `source: <id>@<sha>:<path>` provenance。
     ⚠️ 触碰 config/llm 的 system prompt = 必须同步 dify/flows(CI 镜像不变式)。
   - **机制面 m** → 写成提案:建议改什么(引用源文件+行号)、为什么、裁剪方式、
     与成本梯度/stdlib/离线铁律的兼容性。**不改 src/,只出建议。**
4. **沉淀**(不可省,这是复利):把这次的新搜索方法、映射决策、坑,追加进
   miners/<id>.md 的【📓 沉淀日志】,格式 `- <日期> @<sha>: …`。
5. **收口**:向创始人输出一页报告——promote 候选清单(逐条等点头)+ 机制提案清单
   (等排期)+ 本次沉淀摘要。**promote 永远 HITL、一次一条。**

## 铁律(违反即停)

- 只挖不跑:不执行镜像内代码、不装其依赖、不 pip install 任何东西。
- 引用不吞并:产出落 idea-factory 自己的树,绝不回写 `reference/mirrors/` 内部。
- license:`mirror: false` 源零代码接触;langfuse 的 `ee/`、litellm 的 `enterprise/`
  等商业子目录不读;license 存疑先读 LICENSE 原文再动手。
- 抄任何代码进 `src/`(哪怕纯函数)都要创始人在会话内点头(CLAUDE.md 硬规则)。

## 不带 id 调用时

列出 sources.yaml 全部源(id · lanes · status · 有无镜像 · 有无 miners 文档),
标出"有上游 diff 待评估"和"从未挖过"的,供创始人挑。
