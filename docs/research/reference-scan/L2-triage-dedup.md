---
doc: research
lane: L2
title: "triage:去重与硬过滤"
date: 2026-07-07
agent: subagent
---

# L2 triage:去重与硬过滤

## 结论速览

Top 3:**hf-datatrove**(MinHash-LSH 四阶段管线,机制与我们"每段边界落盘工件"同构,算法可整体抄成 stdlib 纯函数)、**simhash-1e0ng**(本 lane 唯一"已经就是纯 stdlib"的 adopt 级候选,SimhashIndex 是跨周 seen-store 的现成答案)、**ekzhu-datasketch**(阈值→(b,r) 参数的 `_optimal_param` 数学是"阈值设计"问题的标准答案,2026-07 仍在发版)。

最重要的发现:**MinHash-LSH 的全部核心算法(shingle 哈希、universal hashing 置换、banding、union-find)在我们的量级(每次跑几百条信号)下都能用 <150 行 stdlib Python 复刻**,numpy 只是大规模场景的向量化优化——"能否抄成纯 stdlib 函数"的答案是明确的 **能**。次要发现:①语义去重的"便宜预筛 + pair 判定"范式(blocking→只对候选对做贵判定)在开源里以 embedding 形态存在(semhash),LLM-pair 形态尚无权威开源仓,但范式与成本梯度第一原则完全同构,可直接自实现;②规则红线引擎方向是死胡同——现存 rules-engine 项目要么停更要么对"5 条红线"过度工程,我们现有的 `常量 reason code + (kept, killed:dict) 返回 + ledger 落账` 已是业界同款形态(datatrove 的 filter block 也是"排除文档带 reason 写 exclusion writer")。

现状基线(评估时的参照):`stages/triage/dedup.py` 是 O(n²) token-set Jaccard(CJK 按字切分),当前量级够用;LSH 的价值点在**跨周持久 seen 库**长大之后(数千条以上指纹)避免每次全量两两比对。

## 推荐候选(Top 2–3,按价值排序)

### hf-datatrove
- repository: github.com/huggingface/datatrove
- stars: ~3.1k · license: Apache-2.0 · 活跃度: 活跃,v0.9.0 2026-03-04 发布,725 commits,HuggingFace 官方维护
- mined_for:
  - 数据面: MinHash 默认参数组(`num_buckets=14, hashes_per_bucket=8`,共 112 个哈希,对应 Jaccard 阈值 ≈0.72)可直接进 `config/funnel.json` 作为近重阈值的出厂默认
  - 机制面: ①四阶段 MinHash dedup 设计(Signature→Buckets→Cluster→Filter),每阶段读写磁盘中间文件,与我们"阶段边界落盘工件"完全同构,是未来 seen 库规模化时 triage 内部的施工图;②universal hashing 置换 `(shingle*a + b) % ((1<<61)-1)`;③带路径压缩的 union-find 聚类(~15 行纯函数);④filter 阶段把被杀文档连同 removal reason 写 exclusion writer——与我们 killed→ledger impressions 的"杀掉也要留痕"设计互相印证
- 挖什么: `src/datatrove/pipeline/dedup/minhash.py`(签名计算、`_mersenne_prime = (1 << 61) - 1`、bucket 归并用 heapq、union-find);`src/datatrove/pipeline/dedup/sentence_dedup.py` 与 bloom filter 实现(精确层去重的第二参照);`examples/` 下 minhash 全流程编排。移植要点:shingle 哈希用 stdlib `hashlib.sha1(...).digest()[:8]` 转 uint64 即可,numpy 向量化在我们量级直接退化为 for 循环,无性能问题
- SKIP 什么: 整个 executor/分布式层(local/slurm/ray)、fsspec 文件抽象、trafilatura 抽取——全是大规模语料基建,与 triage 无关;不要引 datatrove 为依赖
- 坑: 签名计算里 32/64-bit precision 可配,抄的时候钉死 64-bit 一种;它的 shingle 是面向英文语料的 word n-gram,移植时要接我们 `runtime/textsim.py` 的 CJK 按字 tokenizer,n-gram 粒度(建议字级 3–5 gram)需自己用夹具标定
- recommendation: concepts-borrow(算法级抄纯函数)
- 理由: 工业级验证(FineWeb 谱系)的 MinHash-LSH 完整机制,单文件可读,活跃 org 背书,且四阶段落盘设计天然对齐我们的架构
- 与硬约束的冲突: 依赖 numpy/fsspec——通过"抄算法为 stdlib 纯函数、不引包"裁剪;成本梯度无冲突(全程零 LLM,正是"便宜杀"的教科书);license 无冲突

### simhash-1e0ng
- repository: github.com/1e0ng/simhash
- stars: ~1.0k · license: MIT · 活跃度: **单作者,停更(最后 commit 2022-03)**;但算法实现完整稳定(Google simhash 论文的忠实实现),停更对"只挖不跑"几乎无损
- mined_for:
  - 数据面: 无
  - 机制面: ①Simhash 指纹:特征 md5(stdlib hashlib)→加权比特投票→64-bit 指纹;②**SimhashIndex**:把 64-bit 指纹切成 k+1 块、按(块值,位置)建 dict 索引,查 Hamming 距离 ≤k 的近重是 O(1) 级——这是"跨周持久 seen 库"的现成答案:每周只需在 jsonl 里存一列 int 指纹,增量查重不必重算历史全量
- 挖什么: `simhash/__init__.py`(整个库就一个文件,~200 行):`build_by_features` 的加权投票、`distance` 的 Hamming 计算(可再简化为 `bin(a^b).count("1")` 或 3.10+ 的 `int.bit_count()`)、`SimhashIndex.get_near_dups/add/delete` 的分块索引。tokenizer 是调用方提供的,我们的 `runtime/textsim.py`(CJK 按字)可直接插入
- SKIP 什么: README 里默认的"lowercase alnum 4-gram 滑窗"英文向 tokenize 示例(对中文信号不适用);PyPI 打包与 release 脚本
- 坑: 单作者停更,issue 无人应答——抄进来后即由我们自养,不能指望上游修 bug;simhash 对**短文本**(如一句话 pain_statement)区分度弱于 MinHash/Jaccard,适合做 seen-store 的粗筛层而非唯一判据;md5 可换 `hashlib.blake2b` 提速但要全库一致否则指纹不可比
- recommendation: adopt(唯一可近乎原样抄入的候选:纯 stdlib、单文件、MIT)
- 理由: 本 lane"抄成纯 stdlib 函数"要求的天花板样本——它本来就是,且 SimhashIndex 直接解决跨周 seen 库的增量查重
- 与硬约束的冲突: 无(纯 stdlib、离线、零 LLM、MIT)

### ekzhu-datasketch
- repository: github.com/ekzhu/datasketch
- stars: ~2.9k · license: MIT · 活跃度: 活跃,v2.0.0 2026-07-05 发布(**注意:2.0 改了 MinHash 置换方案**)
- mined_for:
  - 数据面: 无
  - 机制面: ①`lsh.py::_optimal_param`:给定 Jaccard 阈值与 FP/FN 权重,网格搜索最优 (b, r) 并数值积分算误报/漏报概率——这是"阈值设计"从拍脑袋变成可解释推导的标准答案,值得抄成 stdlib 纯函数放 `factors/` 或 triage 内部(scipy 的 quad 换成 ~10 行中点法/梯形积分即可);②MinHashLSH 的 banding 存储形态(每 band 一个 dict,band 内 key=行哈希元组)是最干净的内存版参照;③LSH Ensemble 的 **containment**(包含度)检索概念:两条信号长度悬殊时 Jaccard 天然偏低,containment 是"短信号被长信号包含"这类重复的正确度量——我们信号源长短混杂,这是阈值设计里值得记录的盲区
- 挖什么: `datasketch/lsh.py`(`_optimal_param`/`_false_positive_probability`/`_false_negative_probability`/`_integration` 与 insert/query 主体)、`datasketch/minhash.py`(update/合并逻辑作 datatrove 的交叉校验)、`datasketch/lshensemble.py`(只借 containment 概念)
- SKIP 什么: Redis/Cassandra 存储后端、HyperLogLog、HNSW、Weighted MinHash——全部超出 triage 需求;不要引 datasketch 为依赖(numpy/scipy 硬依赖)
- 坑: v2.0.0(2026-07-05)刚改了置换方案,新旧版本指纹不兼容——挖矿时**钉死 commit**,并在移植笔记里写明抄的是哪个方案;文档部分示例仍是 1.x 语义
- recommendation: concepts-borrow
- 理由: MinHash-LSH 的社区权威参照(datatrove/text-dedup 的 optimal_param 皆源于此),阈值→参数的推导函数是本 lane 独有的可抄资产
- 与硬约束的冲突: numpy/scipy 依赖——只抄 `_optimal_param` 系(纯 Python + 把 scipy 积分换 stdlib 数值积分);无 license/成本梯度冲突

### 附:语义去重"便宜预筛 + pair 判定"范式(无单一权威仓,记入机制结论)

开源现状:embedding 形态的范式由 MinishLab/semhash 代表(blocking 用 ANN,阈值可事后 `rethreshold()` 复核);LLM-pair 形态(块内候选对→便宜模型判"同一机会?")只有闭源服务(everyrow.io)和实体解析文献,**没有值得登记的开源源**。但范式本身与成本梯度第一原则同构,自实现路径明确:精确 dedup_key → Jaccard/LSH 词面预筛(免费)→ 仅存活的高相似候选对进便宜 LLM batch 判定(每对一次小模型调用,量级 O(候选对) 而非 O(n²))。落点是 triage 的可选第三层,`config/llm/` 加一个 pair-judge step;semhash 的 `DeduplicationResult`(selected/filtered + 可解释的重复对 + rethreshold)是这层返回值 schema 的好参照——但 semhash 本体因依赖 model2vec/vicinity 嵌入栈进 skip 清单。

## 评估过但不推荐(skip 清单,防重爬)

- minishlab-semhash(github.com/MinishLab/semhash)— skip:MIT、2026-01 仍发版,但核心价值绑定 model2vec+vicinity 嵌入栈,stdlib/离线铁律下本体不可用;仅借上文所述 DeduplicationResult API 概念与"blocking→复核"范式
- chenghaomou-text-dedup(github.com/ChenghaoMou/text-dedup)— skip:曾是最佳单文件 MinHash 参考(BigCode 谱系),但主干已重写为 Polars+uv 重依赖管线且 release 停在 2023;其经典实现的资产(sha1+Mersenne 置换、optimal_param)已被 datatrove/datasketch 两个更活跃的同谱系源覆盖,挖旧 tag 性价比低
- seatgeek-thefuzz(github.com/seatgeek/thefuzz)— skip:只是 rapidfuzz(C++ 核心)的薄壳;编辑距离类 ratio 对句级近重判定不如 token-set Jaccard/MinHash,且字符级比对需求 stdlib `difflib.SequenceMatcher` 已覆盖
- rapidfuzz(github.com/rapidfuzz/RapidFuzz)— skip:C++ 核心不可 stdlib 移植,理由同上
- beowolx-rensa(github.com/beowolx/rensa)— skip:Rust 核心的 MinHash(卖点是 600x 快),"只挖不跑"下无可读性优势,312 stars 权威度不足
- mattilyra-lsh(github.com/mattilyra/LSH)— skip:Cython+numpy,停更多年,机制被 datatrove 完全覆盖
- allenai-duplodocus(github.com/allenai/duplodocus)— skip:面向大规模数据集批处理的 MinHash 工具,机制与 datatrove 重合且社区小
- nvidia-nemo-curator(github.com/NVIDIA/NeMo-Curator)— skip:模糊/语义 dedup 齐全但绑 GPU/RAPIDS 重型栈,违反 glue-only,只挖不跑成本过高
- google-deduplicate-text-datasets(github.com/google-research/deduplicate-text-datasets)— skip:ExactSubstr 后缀数组,Rust 实现,面向训练语料的子串级去重,与信号级去重问题不匹配
- dedupeio-dedupe(github.com/dedupeio/dedupe)— skip:实体解析+主动学习工作流,numpy/训练环节过重;其 blocking 概念已由 LSH banding 覆盖
- venmo-business-rules(github.com/venmo/business-rules)— skip:规则引擎种子里最知名者,停更近十年
- saurabh0719-py-rules-engine(github.com/saurabh0719/py-rules-engine)— skip:纯 Python 零依赖是加分,但通用规则引擎(JSON 规则树+解析器)对我们个位数红线是过度工程;红线保持"常量 reason code + 纯函数"现状,阈值进 `config/funnel.json` 已足够
- cachecontrol-json-rules-engine(github.com/CacheControl/json-rules-engine)— skip:JavaScript 生态,仅规则 JSON 表达可瞥一眼,无移植价值

## 本 lane 的搜索方法沉淀

- **最高效入口:沿"谱系"挖而不是关键词撒网。** MinHash 去重的开源谱系是 datasketch(算法权威)→ text-dedup/BigCode(单文件化)→ datatrove(工业化四阶段),从任一节点的 README 引用即可走通全链;直接读目标文件(`pipeline/dedup/minhash.py`、`datasketch/lsh.py`)比读 README 信息密度高一个量级
- 有效检索词:`github minhash LSH pure python near-duplicate deduplication`(带 "pure python" 能钓出 1e0ng/simhash 这类真 stdlib 实现)、GitHub topic `minhash?l=python`;WebFetch 直接打 `github.com/<org>/<repo>/blob/main/<file>` 可验证"是否 numpy 依赖"这类关键事实,比看介绍页可靠
- 死胡同一:搜"pure python no dependencies minhash"——搜索结果九成仍是 numpy 系,判断可移植性必须开源码看,不能信描述
- 死胡同二:规则引擎方向(`python rules engine json`)——返回的全是停更或过度工程项目,红线这种规模的需求不存在值得登记的源
- 死胡同三:"LLM pairwise dedup" 开源仓——目前只有闭源产品与论文,无 canonical repo;该范式应记为"自实现+日后复查"而非登记源
- 给未来 miner skill 的提示:datasketch 这类活跃库要**钉 commit**(v2.0.0 刚换置换方案,指纹跨版本不可比);单作者停更库(1e0ng/simhash)适合一次性抄入自养,不适合做持续跟踪源
