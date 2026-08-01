# Agentic RAG(多步检索)eval 报告

> **测试日期**:2026-07-28  
> **版本**:v0.1.0 (44339fa)  
> **decompose 模型**:qwen3:8b + think:false  
> **数据集**:`eval/queries_decompose.jsonl`(9 条对比类 query)  

> **测什么**:对比 deep_search(分解多步+RRF 融合)vs search_notes(单步)。
> **关键指标 recall_all@5**(每个 relevant 都在 top-5):对比类的真正挑战是「双方都召回」,
> recall(any)太宽松(漏一方也算过),recall_all 才看出多步覆盖双方的价值。

## 总体对比

| 方法 | recall@5(any) | recall_all@1 | recall_all@3 | **recall_all@5** | MRR |
|---|---|---|---|---|---|
| 基线(单步 search) | 88.9% | 0.0% | 11.1% | **11.1%** | 0.833 |
| Agentic(多步 decompose) | 88.9% | 0.0% | 33.3% | **33.3%** | 0.833 |

## 逐条明细(分解 + 双方命中,每条标注日期+版本)

| 编号 | query | 子查询数 | 基线双方命中? | deep 双方命中? | 测试日期 | 版本 |
|---|---|---|---|---|---|---|
| T001 | 对比 Transformer 和 RNN | 4 | ✅ | ✅ | 2026-07-28 | v0.1.0 (44339fa) |
| T002 | ReAct 和 Reflexion 的区别 | 3 | ❌ | ❌ | 2026-07-28 | v0.1.0 (44339fa) |
| T003 | CoT 和 Self-Consistency 的关系 | 3 | ❌ | ✅ | 2026-07-28 | v0.1.0 (44339fa) |
| T004 | Function Calling 和 MCP 的关系 | 3 | ❌ | ✅ | 2026-07-28 | v0.1.0 (44339fa) |
| T005 | 对比 Embedding 和 Rerank | 4 | ❌ | ❌ | 2026-07-28 | v0.1.0 (44339fa) |
| T006 | CoT、Self-Consistency 和 Reflexion 三者的关系 | 6 | ❌ | ❌ | 2026-07-28 | v0.1.0 (44339fa) |
| T007 | Embedding、切块和 rerank 三者的关系 | 6 | ❌ | ❌ | 2026-07-28 | v0.1.0 (44339fa) |
| T008 | RAG 是什么以及怎么用 LangGraph 实现 | 1 | ❌ | ❌ | 2026-07-28 | v0.1.0 (44339fa) |
| T009 | ReAct 是什么以及在多智能体里怎么用 | 1 | ❌ | ❌ | 2026-07-28 | v0.1.0 (44339fa) |

## 子查询分解示例

- `对比 Transformer 和 RNN` → ['Transformer 是什么', 'RNN 是什么', 'Transformer 和 RNN 的区别', 'Transformer 和 RNN 的关系']
- `ReAct 和 Reflexion 的区别` → ['ReAct 是什么', 'Reflexion 是什么', 'ReAct 和 Reflexion 的区别']
- `CoT 和 Self-Consistency 的关系` → ['CoT 是什么', 'Self-Consistency 是什么', 'CoT 和 Self-Consistency 的关系']
- `Function Calling 和 MCP 的关系` → ['Function Calling 是什么', 'MCP 是什么', 'Function Calling 和 MCP 的关系']
- `对比 Embedding 和 Rerank` → ['Embedding 是什么', 'Rerank 是什么', 'Embedding 和 Rerank 的区别', 'Embedding 和 Rerank 的关系']

## 说明

- **recall(any)**:top-k 含任一 relevant(宽松,漏一方也算过)。
- **recall_all**(关键):每个 relevant 都在 top-k(对比类真正指标——双方都召回)。
- 预期:对比类 deep 的 recall_all > 基线(多步覆盖 A/B,单步可能只召一方)。
