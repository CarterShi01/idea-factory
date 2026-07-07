# learn-from-fast-map-dpp

## 源速览
- lanes: rank, portfolio · status: adopt · license: Apache-2.0 · pin: true ·
  上游: github.com/laming-chen/fast-map-dpp（镜像 `reference/mirrors/fast-map-dpp` @ 6ab745c）
- 一句话:NeurIPS 2018(Hulu, Chen et al., arXiv 1709.05135)贪心 MAP DPP 的官方参考
  实现,单文件 ~60 行——比 MMR 更原理化的"质量×多样性"子集选择,可把 rank/select 的
  「MMR 软罚 + Jaccard 硬砍」两段补丁与 portfolio/diversify 的配额启发式,升级为单一
  可调目标的选择器。仓库只有算法文件+测试,冻结即完成,停更不构成风险。
- 调研底稿:`docs/research/reference-scan/L4-rank-factors-funnel.md`(fast-map-dpp 节)
  + L7(组合选择交叉推荐)。

## 🔍 搜索方法(怎么在这个 repo 里找)
- 资产定位:**`dpp.py` 是全部价值所在**——核矩阵构造 `L = diag(q)·S·diag(q)` +
  贪心增量选择循环(增量 Cholesky,O(M³))。测试文件可对照验证移植正确性。
- 噪音/陷阱:无可 skip 的部分(仓库极小)。发现路径沉淀:"NeurIPS/KDD 工业论文 +
  第一作者 GitHub"这条路挖到的算法仓通常小而纯,最适合 stdlib 移植。

## 🔗 融合方法(怎么映进 idea-factory)
### 数据面 d
- 无(纯算法仓)。
### 机制面 m → 提案   [proposal-only]
- 映射:质量分 q ← 我们的 alpha;相似度 S ← 复用 rank/select 现有 token-Jaccard
  相似度矩阵;质量-多样性权衡 θ(论文 exp(θ·q))≙ 现有 `diversity_lambda`。
- 落点建议:`stages/rank/select.py` 增加第三选择器(与 MMR/硬去聚类并存,funnel.json
  开关切换,A/B 后再谈替代);portfolio/diversify 的桶内选择同样可换。
- 移植坑(L4 已记):numpy 向量化翻 stdlib 时对角线加 epsilon 保数值稳定;
  q 与 S 的相对尺度需调参。k≤50 规模 O(M³) 无压力。
- ⚠️ 抄入 ~60 行纯函数属"待创始人拍板事项 2"(00-summary §4)——**未点头前不动 src/**。

## 📓 沉淀日志(历次挖矿的决策/坑/映射规则)
- 2026-07-07 @6ab745c:首次登记 + 建镜像(reference 机制落地的全流程示范源)。
  尚未执行首轮挖矿;等创始人对"抄入四个纯函数"批复后跑 `/mine-reference fast-map-dpp`
  出正式移植提案。
