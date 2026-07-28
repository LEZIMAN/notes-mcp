"""Agentic RAG 模块:把检索从「字面匹配」升级为「智能检索」。

分三步走(见 docs/02-设计/迭代计划/AgenticRAG-step1-rewrite_2026-07-27_v0.1.md):
  - Step 1(P0 · 本次):QueryRewriter 查询改写(口语化→正式/补关键词)
  - Step 2(P1 · 后续):多步检索(复杂问题分解)+ history 传递(多轮指代)
  - Step 3(P2 · 后续):自反思(检索够不够判断,引 LangGraph 编排)

设计:Agentic 逻辑封装在 MCP server(智能检索 tool deep_search),Java 后端零改动,
主模型 tool calling 按需调。rewrite/reflect 用本地 qwen3:8b(think:false),跨 Provider 一致。
"""
