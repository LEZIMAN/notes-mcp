# 检索 Eval 报告(纯语义 vs 语义+rerank)

> 正例 45 + 负例 9 + 歧义 5。

## 总体对比

| 方法 | recall@1 | recall@3 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|
| 纯语义 | 57.8% | 93.3% | 100.0% | 100.0% | 0.748 |
| 语义+rerank | 71.1% | 91.1% | 100.0% | 100.0% | 0.825 |

## 按难度 recall@1 / MRR

| 难度 | n | 纯语义 r@1 | +rerank r@1 | 纯语义 MRR | +rerank MRR |
|---|---|---|---|---|---|
| easy | 32 | 53.1% | 68.8% | 0.722 | 0.806 |
| medium | 7 | 57.1% | 71.4% | 0.743 | 0.833 |
| hard | 6 | 83.3% | 83.3% | 0.889 | 0.917 |

## 负例(rerank 后 top-3,检查硬凑)

- `强化学习 PPO 算法` → ['06-Reflexion反思记忆精读.md', '07-RAG检索增强生成精读.md', '01-LLM基本原理-Token-Temperature-Top-P.md']
- `图神经网络 GNN` → ['02-RNN-与-Transformer-的演进.md', '06-The-Illustrated-GPT2-读书笔记.md', '00-索引.md']
- `扩散模型 Diffusion 生成图片` → ['01-config与embedder.md', '03-The-Illustrated-Transformer-读书笔记.md', '01-LLM基本原理-Token-Temperature-Top-P.md']
- `知识图谱 Neo4j 图数据库` → ['07-RAG检索增强生成精读.md', '01-上下文工程.md', '00-索引.md']
- `SVM 支持向量机 原理` → ['03-The-Illustrated-Transformer-读书笔记.md', '03-检索三件套-Chroma-BM25-jieba.md', '08-Embedding与切块策略精读.md']
- `红烧肉怎么做 家常菜谱` → ['05-server.md', '02-Function-Calling-与-Agent.md', '04-search.md']
- `今天上证指数收盘点数` → ['05-Self-Consistency自洽解码精读.md', '08-Embedding与切块策略精读.md', '06-Reflexion反思记忆精读.md']
- `北京明天会下雨吗` → ['01-多工具与-ReAct-循环.md', '02-Function-Calling-与-Agent.md']
- `英超联赛积分榜` → ['04-search.md', '06-The-Illustrated-GPT2-读书笔记.md', '01-config与embedder.md']

## 歧义(rerank 后 top-3)

- `Transformer RAG LangGraph ollama` → ['11-LangGraph进阶-记忆流式并行子图.md', '09-LangGraph状态机精读.md', '00-索引.md']
- `MCP ReAct Function Calling qwen3` → ['12-MCP协议精读.md', '02-本地部署推理Agent-Ollama与Qwen3.md', '01-多工具与-ReAct-循环.md']
- `Token Embedding CoT Reflexion jieba` → ['06-Reflexion反思记忆精读.md', '04-search.md', '00-索引.md']
- `Chroma BM25 RRF bge-m3` → ['02-indexer.md', '04-search.md', '03-检索三件套-Chroma-BM25-jieba.md']
- `LangGraph Checkpointer ReAct Transformer` → ['09-LangGraph状态机精读.md', '10-ReAct智能体精读-从手写到状态机.md', '12-MCP协议精读.md']
