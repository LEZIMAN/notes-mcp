# Agentic RAG(查询改写)eval 报告

> **测试日期**:2026-07-28  
> **版本**:v0.1.0 (c16515e)  
> **rewrite 模型**:qwen3:8b + think:false  
> **数据集**:`eval/queries_rewrite.jsonl`(20 条口语化/关键词不全 query)  

> **测什么**:对比 deep_search(rewrite+search)vs search_notes(基线),
> 验证 rewrite 能否提升口语化 query 的召回。

## 总体对比

| 方法 | recall@1 | recall@3 | recall@5 | MRR |
|---|---|---|---|---|
| 基线(search) | 70.0% | 90.0% | 90.0% | 0.792 |
| Agentic(deep) | 55.0% | 80.0% | 85.0% | 0.677 |

## 逐条明细(改写对比 + rank,每条标注日期+版本)

| 编号 | 原 query | 改写后 | 基线 rank | deep rank | 测试日期 | 版本 |
|---|---|---|---|---|---|---|
| T001 | 咋搞检索增强生成 | 如何实现检索增强生成 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T002 | 那个边想边做的循环 agent | 如何实现 ReAct 循环 agent | rank=1 | rank=5 | 2026-07-28 | v0.1.0 (c16515e) |
| T003 | 反思然后记住教训 | 如何通过反思来记住教训 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T004 | 思考链子是啥 | 思考链是什么 | rank=1 | rank=2 | 2026-07-28 | v0.1.0 (c16515e) |
| T005 | 状态机框架搞 agent | 状态机框架实现 agent | rank=2 | rank=3 | 2026-07-28 | v0.1.0 (c16515e) |
| T006 | 自注意力咋回事 | 自注意力机制原理 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T007 | 温度参数调啥的 | 温度参数如何调整 | 未命中 | 未命中 | 2026-07-28 | v0.1.0 (c16515e) |
| T008 | 本地跑大模型咋弄 | 如何在本地运行大模型 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T009 | 工具调用那个协议 | 工具调用协议 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T010 | 向量数据库存啥的 | 向量数据库存储的内容 | rank=1 | rank=2 | 2026-07-28 | v0.1.0 (c16515e) |
| T011 | 函数调用怎么用 | 如何使用函数调用 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T012 | 生成文本那个搜索算法 | 如何实现生成文本的搜索算法 | rank=2 | rank=2 | 2026-07-28 | v0.1.0 (c16515e) |
| T013 | RSG 检索增强生成 | 检索增强生成 RSG | rank=2 | rank=2 | 2026-07-28 | v0.1.0 (c16515e) |
| T014 | Transfomer 自注意力 | Transformer 自注意力机制 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T015 | React 推理行动循环 | React 推理行动循环 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T016 | Reflection 反思记忆 | Reflection 与反思记忆的关系 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T017 | embeding 向量嵌入 | 向量嵌入 | rank=3 | 未命中 | 2026-07-28 | v0.1.0 (c16515e) |
| T018 | chuncker 切块策略 | Chunker 切块策略 | 未命中 | 未命中 | 2026-07-28 | v0.1.0 (c16515e) |
| T019 | qwen 本地部署推理 | Qwen本地部署推理方案 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |
| T020 | bge 向量模型 | BGE向量模型 | rank=1 | rank=1 | 2026-07-28 | v0.1.0 (c16515e) |

## 说明

- **基线(search)**:Searcher.search(query)(语义 + rerank)。
- **Agentic(deep)**:QueryRewriter.rewrite(query) → Searcher.search(rewritten)。
- 预期:口语化 query,deep 的 recall > 基线(rewrite 补正式术语后命中更好)。
- 若 deep 反而差,说明 rewrite 过度(丢关键词),需调 prompt 或加回退。
