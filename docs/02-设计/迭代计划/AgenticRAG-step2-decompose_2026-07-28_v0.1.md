# Agentic RAG Step 2(多步检索)迭代记录

> **日期**:2026-07-28
> **版本**:v0.1
> **一句话**:对比类 query 分解 + 多步检索 + RRF 融合——做 bge 单轮做不了的事,提升对比类召回。
> **配套**:[Step 1 rewrite 迭代](./AgenticRAG-step1-rewrite_2026-07-27_v0.1.md)(证伪 → 转 Step 2)

---

## 现状

Step 1 rewrite 证伪(qwen3 不比 bge 更懂用户意图,两场景 eval 反降),`deep_search` 代码 + agentic 模块保留。

Step 2 转向 **bge 单轮做不了的事**:对比类 query(「对比 A 和 B」)单轮检索只能找一个语义中心,多步(分别检索 A/B/对比再融合)能覆盖两者。这是 agentic 编排的真增量(对比 rewrite 重复底层能力)。

**decomposer 验证(实施前小规模测试)**:
- ✅ qwen3:8b 对比类(2/3 方、隐含、嵌套、中英)分解正确;多意图/列举拆开;步骤正确不分解。
- ⚠️ 单一问题(否定/深问)**过度分解**成近义重复(如「RAG 不能解决什么」拆成 4 种近义)。
- → Step 2 须设防过度分解。

## 目标

对比类 query → 分解 → 多步检索 → RRF 融合去重,提升对比类召回。

**红线**:decomposer 不能过度分解单一问题(导致多步检索空转同义 query、浪费 + 重复)。

## 改动清单

| # | 改动 | 文件 | 治什么 |
|---|---|---|---|
| 1 | 新增 `QuestionDecomposer`(对比类→子查询) | `notes_mcp/agentic/decomposer.py`(新) | 分解逻辑 |
| 2 | `PROMPT_DECOMPOSE`(强化「单一不分解,禁同义拆」) | `notes_mcp/agentic/prompts.py`(改) | 约束过度分解 |
| 3 | 升级 `deep_search`:decompose → 多步 search → RRF 融合 | `notes_mcp/server.py`(改) | 多步编排 |
| 4 | `_fuse_hits`(RRF + chunk_id 去重) | `notes_mcp/server.py`(改) | 多步结果融合 |
| 5 | eval:对比类数据集 + `eval_agentic` 加分步对比 | `eval/queries_decompose.jsonl` + `scripts/eval_agentic.py`(改) | 量化多步 vs 单步 |

## 决策

| 决策 | 选 | 备选 | 理由 |
|---|---|---|---|
| decomposer 触发 | **检测对比词**(对比/区别/关系/vs/和…哪个)才分解,其余原样 | 全部分解 | 防单一问题过度分解(验证边界) |
| 多步融合 | **RRF**(倒数排名融合)+ chunk_id 去重 | 简单合并 / rerank 分加权 | rerank 分跨 query 不可比;RRF 按排名鲁棒 |
| 编排 | 纯函数(decompose→multi-search→fuse) | LangGraph | Step 2 无循环(Step 3 反思才引) |
| decompose 模型 | 复用 qwen3:8b(同 rewrite_model) | 另配 | 已验证够用;减少配置项 |

## 风险

- **过度分解**(验证发现):三重防护——① 检测对比词才分解 ② prompt 强化「单一不分解,禁同义拆」 ③ 子查询去重。
- **多步检索成本**:对比类 query 多次 search(N 子查询),延迟增。但对比类占比低(多数单一),可接受。
- **decomposer 误判**:极简两词推断对比可能误。少数,可接受。

## 验收(实测 · 正结果)

eval 对比类数据集(`eval/queries_decompose.jsonl`,10 条):deep_search(多步)vs search_notes(单步)。

| 指标 | 基线(单步) | Agentic(多步) |
|---|---|---|
| recall@5(any) | 100.0% | 100.0% |
| **recall_all@5(全命中)** | **40.0%** | **80.0%** |
| MRR | 1.000 | 1.000 |

**recall_all@5(双方都召回):40% → 80%,翻倍(+40pp)!**

这是对比类的真正指标——单步常漏一方(仅 40% 双方都在 top-5),多步分解检索覆盖双方(80%)。recall(any)看不出(都 100%,任一命中太宽松),**recall_all 才体现多步价值**——评估指标必须匹配场景(对比类 = 双方覆盖),否则「两者都满分」误判多步无用(第一轮踩过)。

### 结论

Step 2 多步检索**有效**(recall_all +40pp)。对比 Step 1 rewrite 证伪:decompose 多步做的是 bge 单步做不了的事(覆盖双方),是真增量。**印证 Step 1 教训:agentic 做底层做不了的事才有价值。**

## 启示

1. **Step 1 教训落地**:实施前验证(decomposer 小规模测试)——验证通过(对比类好)+ 暴露边界(单一过度分解),实施时设防。避免重蹈 rewrite(实施完才证伪)。
2. **agentic 做底层做不了的事**:多步检索是 bge 单轮弱项(对比类),agentic 分解+多步是真增量(对比 rewrite 重复底层)。
3. **过度分解防护**:LLM decomposer 倾向「多拆」(尤其否定/深问),需 prompt + 规则 + 去重约束。

## 后续

- **Step 3**:自反思(reflector 判断检索够不够,引 LangGraph 编排循环)——同样验证「反思比底层 score 更准」,避免重蹈 rewrite。
- **history 传递**(多轮指代):留待 Step 2/3 一并解决。
