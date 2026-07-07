# miners/<id>.md 骨架模板(复制本文件、填前两节、日志逐次追加)

> **每个学习源一份挖矿沉淀文档** `reference/miners/<id>.md` —— 这个源的
> 搜索方法(怎么在这个 repo 里找)+ 融合方法(怎么映进 idea-factory)+
> 历次决策/坑。**复利在沉淀日志里**:下次挖同一源不从零开始。
> 挖矿动作由 `/mine-reference <id>` skill 驱动;共享底座(注册表/镜像/纪律)
> 见 `reference/README.md`,不在这里复述。

```markdown
# learn-from-<id>

## 源速览
- lanes: <落哪些模块> · status · license · pin · 上游 repo
- 一句话:这个源是什么、为什么挖它(转录 sources.yaml note + lane 文件结论)
- 调研底稿:docs/research/reference-scan/L<N>-*.md 的对应小节

## 🔍 搜索方法(怎么在这个 repo 里找)      ← per-source 分歧①
- 资产定位:<prompt/schema/纯函数具体在哪个文件;大仓先走哪个 docs/注解仓>
- 噪音/陷阱:<哪些目录别碰(商业 license 子目录/示例/过时);版本重构断层>

## 🔗 融合方法(怎么映进 idea-factory)      ← per-source 分歧②
### 数据面 d → config/ · fixtures 字段规范 · dify/flows   [有门 promote]
- 映射规则:<源对象 → 我们的 prompt/schema/参数怎么改写(中文化/字段对齐/裁剪)>
- 落点与 provenance:<目标文件;头部 `source: <id>@<sha>:<path>` 注释/_source 字段>
- ⚠️ 触碰 config/llm system prompt = 必须同步 dify/flows(镜像不变式,CI 有钉)
### 机制面 m → 提案                        [proposal-only]
- 裁剪成 idea-factory 工件的**建议**(引用源文件+行号)→ 创始人审 → 才改 src/。
  miner 不改 pipeline,只出建议。

## 📓 沉淀日志(历次挖矿的决策/坑/映射规则)  ← 复利在这里,追加不可省
- <日期> @<sha>:<这次挖了什么、定了什么映射、踩了什么坑、创始人裁决>
```
