# Agentic RAG Step 1(查询改写)迭代记录

> **日期**:2026-07-27
> **版本**:v0.1
> **一句话**:MCP server 加 `deep_search` tool,内部 qwen3 改写 query 后检索——提升口语化/关键词不全 query 的召回。Java 零改动。
> **配套**:[意图过滤模型选型](../选型/意图过滤模型选型_2026-07-26_v0.1.md) · [检索 eval 报告](../../04-测试/检索eval_2026-07-26.md) · [实施 plan](../../../../C:/Users/17792/.claude/plans/snug-dreaming-hammock.md)

---

## 现状

notes-mcp 当前是「单轮检索 + 生成」:主模型(Spring AI tool calling)调 MCP `search_notes` 检索 → 生成。检索质量受 query 质量影响:
- 口语化 query(`咋搞 RAG`)召回差
- 关键词不全 / 表述偏离笔记术语 → 召回不到

`search_notes` 是语义检索,不会"理解"query 意图去改写。

## 目标

**Step 1:Query Rewrite**——MCP server 加 `deep_search` tool,内部先用 qwen3:8b 改写 query(口语化→正式、补关键词、规范化),再检索。提升口语化/关键词不全 query 的 recall。

**红线**:deep_search 不能让标准 query 的 recall 下降(rewrite 改写过度会丢关键词)。所以与 search_notes **并存**,主模型按需选。

> ⚠️ **Step 1 不含多轮指代**("它"→具体,需 history)。tool calling 下 history 传参复杂(主模型自主调 tool,history 参数主模型提取不可靠),留 Step 2。Step 1 只测「同轮内,改写能否提升口语化 query 召回」。

## 改动清单

| # | 改动 | 文件 | 治什么 |
|---|---|---|---|
| 1 | 新增 `QueryRewriter` 类(httpx 调 ollama 原生 /api/chat,think:false) | `notes_mcp/agentic/rewriter.py`(新) | 改写逻辑(复用 `eval_intent.py` 范式) |
| 2 | 新增 `PROMPT_REWRITE`(只规范化不改义、补关键词、只输出改写后 query) | `notes_mcp/agentic/prompts.py`(新) | 约束改写质量 |
| 3 | 新增 `deep_search(query, top_k)` tool(rewrite→search→format) | `notes_mcp/server.py`(改) | MCP 暴露 agentic 检索 |
| 4 | `create_mcp` 加 rewriter 参数(闭包注入,同 searcher 模式) | `server.py` + `cli.py`(改) | rewriter 装配 |
| 5 | 新增 `REWRITE_MODEL` 配置(默认 qwen3:8b) | `config.py` + `.env.example` + `配置.md`(改) | 可配置(单一信息源) |
| 6 | 新增 `eval_agentic.py` + `queries_rewrite.jsonl` | `scripts/` + `eval/`(新) | 量化 deep_search vs search_notes |

## 决策

| 决策 | 选 | 备选 | 理由 |
|---|---|---|---|
| Agentic 加哪层 | **MCP server 加 deep_search tool** | Java 后端编排 / 主模型加 tools / agent.py | Java 零改动;复用 qwen3;跨 Provider 一致;生产链路 |
| rewrite 模型 | ollama qwen3:8b + think:false | 主模型 / 别的小模型 | 复用意图过滤层;跨 Provider 一致;免费;think:false 快 |
| deep_search 与 search_notes | **并存**(主模型按需选) | 替换 search_notes | 保留 eval 基线;降风险;主模型按 query 复杂度选 |
| 编排 | Step 1 纯函数(rewrite→search) | LangGraph | Step 1 无循环;Step 3 反思才引 LangGraph |
| 是否含 history(多轮指代) | **不含**(留 Step 2) | 含 history | tool calling 下 history 传参复杂;Step 1 先验证同轮改写 |

## 风险

- **rewrite 过度**(丢关键词):prompt 约束「只规范化不改义」;eval 验证;改写偏离时回退原 query。
- **主模型不选 deep_search**(总调 search_notes):需 system prompt 引导;观察 tool 选择率。
- **rewrite 延迟**(每次 deep_search 多 ~0.6–1s):本地免费;简单 query 主模型应选 search_notes(快)。

## 验收(实测 · 负结果)

`scripts/eval_agentic.py` 对比 deep_search vs search_notes。**两轮 eval 均证伪 rewrite 价值**。

### 第一轮:口语化 query(12 条)

| 方法 | recall@1 | recall@3 | recall@5 | MRR |
|---|---|---|---|---|
| 基线(search) | 75.0% | 91.7% | 91.7% | **0.833** |
| Agentic(deep) | 50.0% | 83.3% | 91.7% | 0.669 |

deep recall@1 **反降 25%**。

### 第二轮:加 typo/偏移关键词(共 20 条)

| 方法 | recall@1 | recall@3 | recall@5 | MRR |
|---|---|---|---|---|
| 基线(search) | 70.0% | 90.0% | 90.0% | **0.792** |
| Agentic(deep) | 55.0% | 80.0% | 85.0% | 0.677 |

deep 仍差。且 typo 条 rewrite 多没纠正(`RSG`→`检索增强生成 RSG` 没纠 RAG;`React`/`Reflection` 原样),只有明显拼写错(`Transfomer`/`chuncker`)纠正。

### 根因(为什么 rewrite 无效)

1. **bge-m3 已强**:口语化 + 明显拼写错它直接能召回,query 没那么「差」。
2. **qwen3 不纠错术语**:看到 `RSG` 不知用户 meant `RAG`——rewrite 模型(qwen3:8b)和检索模型(bge-m3)语义能力相当,**不比 bge 更懂用户意图**。rewrite 要有效得有「比 bge 更懂用户想问什么」的能力,qwen3:8b 不具备。
3. **rewrite 改写偏离笔记术语**(口语化场景):往通用正式语改,离笔记原文(`检索三件套`/`Function Calling 与 Agent`)更远。

### 结论

rewrite 在「强语义检索(bge-m3)+ 同级改写模型(qwen3:8b)」组合下**无价值**。Step 1 证伪。`deep_search` 代码保留(Step 2/3 复用基础设施),但主模型默认用 `search_notes`。

## 启示

1. **Agentic 能力封装在 MCP tool**(智能检索 deep_search),主模型按需调——比改 Java 后端轻得多,符合 MCP 架构哲学。
2. **rewrite 不依赖主模型**(用固定 qwen3),跨 Provider 一致——Agentic 逻辑下沉到检索层,不随主 provider 变。
3. **Step 分解**(rewrite → 多步 → 反思),每步可 eval 验证,避免一次性做太大。
4. **skill 自动触发不可靠**:开始大改前应主动调 dev-doc 写迭代记录,不等 skill 触发(本次教训——dev-doc 靠 description 关键词匹配,「做 RAG/方案拟定」没命中,漏了)。
5. **eval 证伪假设是正常的**(本次核心教训):Step 1 假设「rewrite 提升低质量 query 召回」,两轮 eval(口语化 + typo)证伪。根因——改写模型(qwen3)和检索模型(bge-m3)能力相当时,改写无增量信息(不比 bge 更懂用户意图)。价值:避免盲目加 rewrite 降质量。**下次先想清楚「这个 agent 能力是否比底层模型更懂某事」,否则就是空转。**

## 后续(转 Step 2)

Step 1 rewrite 证伪,转 **Step 2:多步检索**(针对对比类 query,如「对比 Transformer 和 RNN」)。

为什么 Step 2 更可能有效(rewrite 的反面):
- rewrite 失败因「qwen3 不比 bge 更懂用户意图」——改写是 bge 已能做的事的重复;
- **多步检索是 bge 单轮做不了的事**——「对比 A 和 B」需分别检索 A、B 再综合,bge 单轮检索只能找一个语义中心,天然弱。这是 agentic 编排真正的增量价值(做底层模型做不了的事,而非重复)。

Step 2 计划:问题分解(对比类 → 子查询)+ 多步检索 + 结果融合(RRF/去重)。history 传递(多轮指代)留 Step 2 一并解决。

- **Step 3**:自反思(reflector 判断检索够不够,引 LangGraph 编排循环)——同样要验证「反思是否比底层 score 更准」,避免重蹈 rewrite 覆辙。
