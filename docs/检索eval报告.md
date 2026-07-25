# 检索 Eval 报告(纯语义)

> 正例 45 条(分难度) + 负例 9 条 + 歧义 5 条。

## 按难度分组(正例)

| 难度 | 样本 | recall@1 | recall@3 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| easy | 32 | 53.1% | 93.8% | 100.0% | 100.0% | 0.722 |
| medium | 7 | 57.1% | 85.7% | 100.0% | 100.0% | 0.743 |
| hard | 6 | 83.3% | 100.0% | 100.0% | 100.0% | 0.889 |
| 总计 | 45 | 57.8% | 93.3% | 100.0% | 100.0% | 0.748 |

## 负例(完全无关,测 precision——不该硬凑)

- `强化学习 PPO 算法` → top3: ['03-The-Illustrated-Transformer-读书笔记.md', '01-LLM基本原理-Token-Temperature-Top-P.md', '06-Reflexion反思记忆精读.md']
- `图神经网络 GNN` → top3: ['02-RNN-与-Transformer-的演进.md', '00-索引.md', '06-The-Illustrated-GPT2-读书笔记.md']
- `扩散模型 Diffusion 生成图片` → top3: ['03-The-Illustrated-Transformer-读书笔记.md', '00-索引.md', '04-多智能体.md']
- `知识图谱 Neo4j 图数据库` → top3: ['00-整体介绍.md', 'Continue本地补全配置方案.md', '04-多智能体.md']
- `SVM 支持向量机 原理` → top3: ['03-The-Illustrated-Transformer-读书笔记.md', '08-Embedding与切块策略精读.md', '05-Spec-driven.md']
- `红烧肉怎么做 家常菜谱` → top3: ['11-LangGraph进阶-记忆流式并行子图.md', '05-server.md', '04-search.md']
- `今天上证指数收盘点数` → top3: ['03-The-Illustrated-Transformer-读书笔记.md', '08-Embedding与切块策略精读.md', '06-Reflexion反思记忆精读.md']
- `北京明天会下雨吗` → top3: ['01-多工具与-ReAct-循环.md', '02-Function-Calling-与-Agent.md']
- `英超联赛积分榜` → top3: ['09-LangGraph状态机精读.md', '03-The-Illustrated-Transformer-读书笔记.md', '04-search.md']

## 歧义(术语堆砌无意图,测意图识别——应提示细化)

- `Transformer RAG LangGraph ollama` → top3: ['10-ReAct智能体精读-从手写到状态机.md', '11-LangGraph进阶-记忆流式并行子图.md', '09-LangGraph状态机精读.md']
- `MCP ReAct Function Calling qwen3` → top3: ['02-本地部署推理Agent-Ollama与Qwen3.md', '12-MCP协议精读.md', 'Continue本地补全配置方案.md']
- `Token Embedding CoT Reflexion jieba` → top3: ['04-search.md', '06-Reflexion反思记忆精读.md', '03-检索三件套-Chroma-BM25-jieba.md']
- `Chroma BM25 RRF bge-m3` → top3: ['03-检索三件套-Chroma-BM25-jieba.md', '04-search.md', '02-indexer.md']
- `LangGraph Checkpointer ReAct Transformer` → top3: ['09-LangGraph状态机精读.md', '00-索引.md', '10-ReAct智能体精读-从手写到状态机.md']

## 改进方向

- **hard 题** recall/MRR 最能体现检索质量,是 rerank 的主战场。
- **负例**全硬凑 → 需 score 阈值过滤(不相关的不返回)。
- **歧义**词相关无意图 → 产品应提示「请明确你想了解哪一个」。
- 加 rerank + score 阈值后在此报告对比。
