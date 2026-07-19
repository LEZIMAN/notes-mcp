# notes-mcp

> 把一个或多个 markdown 笔记目录变成一个 **MCP 知识助手 server**——不只「查得到」笔记,更把笔记变成**可用的结果**(讲解 / 复习提纲 / 自测题 / 对比表……),让所有支持 MCP 的 AI 工具(Claude Desktop / Cursor / 自写 agent)直接复用。
>
> **一处实现,处处可用。**

---

## 这是什么

`notes-mcp` 是一个基于 [MCP 协议](https://modelcontextprotocol.io)(Model Context Protocol,Anthropic 2024-11 开放协议)的**知识库 server**。你给它**一个或多个** markdown 笔记目录(笔记分散在多处也没关系),它:

1. **自动建库**:扫目录 → 切块 → 向量嵌入(语义)+ 关键词索引(BM25)
2. **标准化暴露**:按 MCP 协议把「查笔记」的能力(tools / resources / prompts)暴露出去
3. **任意 client 复用**:Claude Desktop、Cursor、MCP inspector、自写 agent……任何 MCP client 接上就能查,不用每个工具各搞一套 RAG

> 💡 比喻:**USB-C 之于设备,notes-mcp 之于「笔记 + AI 工具」**——笔记方按标准协议供给,AI 工具方按标准协议消费。

---

## 解决什么问题

作为一个 AI 方向的学习者,我积累了大量 markdown 笔记(LLM / Transformer / RAG / ReAct / LangGraph……)。问题是:

| 痛点 | 现状 | notes-mcp 怎么解 |
|---|---|---|
| 笔记越多越难找 | 全文搜索没语义、查不到「意思相近」的 | **hybrid search**(语义 + 关键词融合) |
| 工具碎片化 | Cursor / Claude / Obsidian 各不知道我的笔记 | 笔记封成 **MCP server**,所有工具统一查 |
| 每接一个工具要重做 RAG | 每个 agent 各写一套检索 | **一处实现,处处可用**(MCP 核心卖点) |
| 答案没出处 | LLM 可能瞎编 | 结果**带溯源**(来源文件 + 标题) |

---

## 怎么工作

```
                你的 markdown 笔记目录
                         │  notes-mcp server 启动时自动建库
                         ▼
        ┌────────────────────────────────────┐
        │   notes-mcp server(FastMCP)        │
        │   · Chroma 向量库(语义检索)        │
        │   · BM25 索引(关键词检索)          │
        │   · SQLite 增量状态(只更新变化)    │
        │                                    │
        │   暴露三大原语:                     │
        │     Tools    / Resources / Prompts │
        └────────────────────────────────────┘
            │ MCP 协议(stdio 本地 / HTTP 远程)
   ┌────────┼────────────────────────┐
   ▼        ▼                        ▼
Claude    Cursor              自写 LangGraph agent
Desktop                       (同时消费 notes-mcp + filesystem + fetch)
```

**核心思想**:笔记库 = 一个标准 MCP server,工具供给与 AI 工具解耦。换笔记目录、换 AI 工具,互不影响。

---

## 提供什么(MCP 三大原语齐全)

| 原语 | 名称 | 谁控制 | 干什么 |
|---|---|---|---|
| **Tool** | `search_notes(query)` | 🤖 模型 | **hybrid 检索**(语义 + BM25 + RRF 融合),返回带出处 |
| **Tool** | `get_note(title)` | 🤖 模型 | 按标题取整篇笔记 |
| **Tool** | `list_topics()` | 🤖 模型 | 列出所有笔记标题/主题 |
| **Resource** | `notes://stats` | 📦 应用 | 知识库统计(笔记数、chunk 数、模型、最近更新) |
| **Resource** | `notes://index` | 📦 应用 | 笔记目录树 |
| **Resource** | `notes://note/{title}` | 📦 应用 | **模板 URI**:按标题取单篇(RFC 6570 参数化) |
| **Prompt** ⭐ | `explain(concept)` | 👤 用户 | 检索+组织成**讲解** · 核心 |
| **Prompt** ⭐ | `review(topic)` | 👤 用户 | **复习提纲 + 自测题** · 核心 |
| **Prompt** ⭐ | `quiz(topic)` | 👤 用户 | **出题**测掌握度 · 核心 |
| **Prompt** ⭐ | `compare(a, b)` | 👤 用户 | 制**对比表**辨析 · 核心 |
| **Prompt** | `connect(topic)` | 👤 用户 | 找跨笔记**关联** |
| **Prompt** | `apply(problem)` | 👤 用户 | 用笔记**分析问题** |
| **Prompt** | `summarize(target)` | 👤 用户 | **浓缩摘要** |

> 🔑 **三层金字塔 = 找 → 拿 → 用**:Tools「找」(LLM 拉)、Resources「拿」(应用推)、**Prompts「用」(用户选「拿笔记干嘛」)**——Prompts 才是「记笔记有什么用」的答案,也是本项目区别于普通检索工具的核心。
>
> ⚙️ 控制权归属:Tools = model-controlled、Resources = application-controlled、Prompts = user-controlled(MCP 三大原语的设计本质)。

---

## 技术亮点

1. **不止检索,是「知识助手」(找→拿→用闭环)**——不只「找」笔记,更用 Prompts 把笔记变成讲解 / 复习提纲 / 自测题 / 对比表(应用层),这才是「记笔记有什么用」;Tools / Resources / Prompts 三大原语齐全。
2. **Hybrid Search**——语义检索(bge-m3 embedding)+ 关键词检索(BM25 + jieba 中文分词)+ RRF 融合,落地 RAG「hybrid + rerank」理论,比纯语义或纯关键词都准。
3. **自动增量建库**——FastMCP `lifespan` 机制,server 启动时一次性建库;SQLite 追踪文件 mtime/hash,只更新变化的笔记,不用手动跑建库脚本。**支持多目录扫描**(笔记分散在多处,`;` 分隔),自动排除 `venv` / `node_modules` / `.git` / `__pycache__` 等依赖目录。
4. **双传输**——`stdio`(本地,被 Claude Desktop/inspector 调)+ `Streamable HTTP`(远程,多 client 共享)。
5. **溯源**——每条检索结果带来源文件 + 标题,LLM 答得有依据,方便核对。
6. **通用 + 可开源**——不绑定某一组笔记,任意 markdown 目录即插即用;CLI + 配置化。

---

## 快速开始(预览)

> Phase 1 核心闭环已实现(config→indexer→search→server→cli),以下为实际用法。

```bash
# 1. 安装
cd 项目/notes-mcp
python -m venv venv && venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 2. 配置(指向你的笔记目录,支持多个,用 ; 分隔)
cp .env.example .env
#   NOTES_DIR=d:/Learn/AI/笔记;d:/Learn/AI/项目/rag-agent/docs
#   OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
#   EMBED_MODEL=bge-m3

# 3. 跑 server(本地 stdio,给 Claude Desktop / inspector 用)
python -m notes_mcp serve --transport stdio

# 或远程 HTTP
python -m notes_mcp serve --transport http --port 8765
```

**接到 Claude Desktop**(`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "notes-mcp": {
      "command": "python",
      "args": ["-m", "notes_mcp", "serve", "--transport", "stdio"]
    }
  }
}
```

**调试**:`npx @modelcontextprotocol/inspector python -m notes_mcp serve --transport stdio`

---

## 开发(lint / 测试 / 提交钩子)

> 工程地基已就位(详见 [开发规范](./docs/开发规范.md))。开发依赖装好后,常用命令统一走 `scripts/dev.py`(Windows 友好、零第三方依赖):

```bash
# 1. 装开发依赖(ruff / mypy / pre-commit / pytest)
venv/Scripts/python -m pip install -r requirements-dev.txt

# 2. 装 git 提交钩子(一次即可;之后每次 commit 自动 lint + type)
python scripts/dev.py install-hooks

# 3. 日常开发(激活 venv 后运行)
python scripts/dev.py lint        # ruff 静态检查
python scripts/dev.py format      # ruff 格式化(自动改)
python scripts/dev.py type        # mypy 类型检查(notes_mcp)
python scripts/dev.py test        # pytest 单元+集成(用 fake embedder,快)
python scripts/dev.py coverage    # pytest + 覆盖率报告
python scripts/dev.py check-sync  # 校验核心依赖/配置齐全(防文档漂移)
```

提交前检查清单见 [开发规范 §8](./docs/开发规范.md)。CI 待开源/push 时再加。

---

## 项目结构

```
notes-mcp/
├── notes_mcp/
│   ├── server.py        # FastMCP server:三大原语 + lifespan 建库 + 双传输
│   ├── indexer.py       # 扫目录 + 切块 + Chroma + BM25 + SQLite 增量
│   ├── search.py        # hybrid:语义 + BM25 + RRF 融合
│   ├── embedder.py      # OllamaEmbedder(bge-m3)
│   ├── cli.py           # CLI:serve / index / query
│   └── config.py        # 读 .env
├── agent.py             # 消费侧 LangGraph agent(命令行)
├── web/                 # Web 全栈 UI(FastAPI 后端 + React 前端)
├── docs/                # 需求分析 + 设计文档 + 开发规范 + 配置
├── tests/               # RRF / hybrid 单测
├── examples/            # claude_desktop_config.json + demo 问题
├── .env.example
├── requirements.txt
└── README.md
```

---

## 与学习笔记的关系

这个项目是 **AI 学习工作区**「Agent 核心」线的工程落地(项目实战 P3),与一组精读笔记呼应:

| 笔记 | 在本项目哪里用到 |
|---|---|
| [笔记⑳ MCP 协议精读](../../笔记/Agent核心/04-框架/12-MCP协议精读.md) | 整个项目的理论根基:三大原语、Host/Client/Server、双传输 |
| [笔记 07 RAG / 08 Embedding&切块](../../笔记/Agent核心/03-RAG/) | hybrid search、切块策略、embedding、溯源 |
| [笔记 09–11 LangGraph](../../笔记/Agent核心/04-框架/) | 消费侧 agent 的 ReAct 状态机(图结构 + 回边) |

---

*项目状态:✅ Phase 1 核心闭环完成(config / chunker / embedder / indexer / search / server / cli,88 tests 全绿)· 2026-07-19 · 下一阶段:Phase 2 消费侧 LangGraph agent*
