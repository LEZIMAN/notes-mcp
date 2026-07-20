# notes-mcp

> 把一个或多个 markdown 笔记目录变成一个 **MCP 知识助手 server**——不只「查得到」笔记,更把笔记变成**可用的结果**(讲解 / 复习提纲 / 自测题 / 对比表……),让所有支持 MCP 的 AI 工具(Claude Desktop / Cursor / 自写 agent)直接复用。
>
> **一处实现,处处可用。**

---

## 这是什么

`notes-mcp` 是一个基于 [MCP 协议](https://modelcontextprotocol.io)(Model Context Protocol,Anthropic 2024-11 开放协议)的**知识库 AI 助手**。你给它**一个或多个** markdown 笔记目录(笔记分散在多处也没关系),它:

1. **自动建库**:扫目录 → 切块 → 向量嵌入(语义)+ 关键词索引(BM25)
2. **标准化暴露**:按 MCP 协议把「查笔记」的能力(tools / resources / prompts)暴露出去
3. **Web UI**:React 前端 + Spring Boot 后端,浏览器直接对话,支持多 Provider
4. **多 Provider**:本地 Ollama + OpenAI + 自定义 OpenAI 兼容端点(DeepSeek / Groq / vLLM 等)
5. **任意 client 复用**:Claude Desktop、Cursor、MCP inspector、自写 agent……任何 MCP client 接上就能查

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
| 本地 + 云端切换 | 免费时用本地,复杂任务用付费 API | **一键切换 Provider**(Ollama / OpenAI / 自定义) |

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
            │ MCP 协议(stdio)
            ▼
┌──────────────────────────────────────────────┐
│       Spring Boot 后端(port 8000)            │
│       · ProviderRouter(多 Provider 路由)      │
│       · ChatHistoryService(对话记录 SQLite)  │
│       · MCP client(调用 notes-mcp 工具)      │
└──────────────────────────────────────────────┘
            │ REST API(/api/*)
            ▼
┌──────────────────────────────────────────────┐
│       React 前端(port 5173)                  │
│       · 三栏布局(侧边栏/对话/信息)           │
│       · 设置中心(Provider/模型/笔记目录)     │
│       · 学习模式(讲解/复习/自测/对比)        │
│       · 笔记详情页(Markdown 渲染)            │
│       · 对话记录持久化                        │
└──────────────────────────────────────────────┘
```

**核心思想**:笔记库 = 一个标准 MCP server,工具供给与 AI 工具解耦。前端直接对话,底层通过 ProviderRouter 无缝切换本地/云端模型。

---

## 提供什么

### MCP 三大原语(协议层)

| 原语 | 名称 | 谁控制 | 干什么 |
|---|---|---|---|
| **Tool** | `search_notes(query)` | 🤖 模型 | **hybrid 检索**(语义 + BM25 + RRF 融合),返回带出处 |
| **Tool** | `get_note(title)` | 🤖 模型 | 按标题取整篇笔记(支持 H1 标题和文件名) |
| **Tool** | `list_topics()` | 🤖 模型 | 列出所有笔记标题/主题 |
| **Resource** | `notes://stats` | 📦 应用 | 知识库统计(笔记数、chunk 数、模型) |
| **Resource** | `notes://note/{title}` | 📦 应用 | 模板 URI:按标题取单篇 |
| **Prompt** | `explain / review / quiz / compare` | 👤 用户 | 讲解 / 复习 / 自测 / 对比——**Prompts 是应用层核心** |

### Web API(REST 层)

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/chat` | POST | 智能对话(支持 sessionId 持久化) |
| `/api/search` | GET | 直接搜索笔记 |
| `/api/notes/{title}` | GET | 取笔记原文 |
| `/api/notes/tree` | GET | 笔记文件夹树结构 |
| `/api/topics` | GET | 笔记标题列表 |
| `/api/stats` | GET | 知识库统计 |
| `/api/settings` | GET/PUT | 获取/更新完整配置 |
| `/api/models` | GET | 当前 Provider 可用模型 |
| `/api/models/select` | POST | 切换模型 |
| `/api/models/refresh` | POST | 刷新模型列表 |
| `/api/provider/select` | POST | 切换 Provider |
| `/api/sessions` | GET/POST | 会话列表/新建 |
| `/api/sessions/{id}` | GET/DELETE | 获取/删除会话 |

---

## 技术亮点

1. **完整 Web UI**——React 三栏布局 + 设置中心 + 学习模式 + 笔记详情 + 对话记录
2. **多 Provider 支持**——Ollama 本地 / OpenAI / 自定义端点(DeepSeek, Groq, vLLM...),一键切换
3. **Hybrid Search**——语义(bge-m3)+ 关键词(BM25 + jieba)+ RRF 融合
4. **增量建库**——SQLite 追踪 mtime/hash,只更新变化的笔记
5. **溯源**——每条结果带来源文件 + 标题
6. **对话持久化**——SQLite 存储会话和消息,支持历史查看
7. **双传输**——stdio(本地 MCP)+ Streamable HTTP(远程)

---

## 快速开始

### 前置条件

- Java 17+、Maven 3.9+
- Python 3.10+、Node.js 18+
- Ollama(本地模型)或 API Key(OpenAI / DeepSeek)

### 1. Python MCP Server

```bash
cd notes-mcp
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
# 编辑 .env:NOTES_DIR=d:/你的笔记目录
python -m notes_mcp index   # 首次建库
```

### 2. Spring Boot 后端

```bash
cd web/backend
mvn spring-boot:run
# 启动在 http://localhost:8000
```

### 3. React 前端

```bash
cd web/frontend
npm install
npm run dev
# 启动在 http://localhost:5173
```

### 4. 配置 Settings

打开浏览器访问 `http://localhost:5173` → 点击右上齿轮图标 → 设置笔记目录、选择 Provider(Ollama/OpenAI/自定义)、选择模型。

### 接到 Claude Desktop

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

---

## 项目结构

```
notes-mcp/
├── notes_mcp/              # Python MCP Server
│   ├── server.py           # FastMCP:三大原语 + lifespan 建库
│   ├── indexer.py          # 增量建库(Chroma + BM25 + SQLite)
│   ├── search.py           # Hybrid 检索(RRF 融合)
│   ├── embedder.py         # OllamaEmbedder(bge-m3)
│   ├── chunker.py          # Markdown 切块
│   ├── cli.py              # CLI:serve / index / query
│   └── config.py           # 读 .env
├── web/
│   ├── backend/            # Spring Boot 后端
│   │   └── src/main/java/com/notesmcp/backend/
│   │       ├── ProviderRouter.java    # 多 Provider 路由
│   │       ├── SettingsService.java   # 配置管理
│   │       ├── ChatHistoryService.java # 对话记录 SQLite
│   │       ├── ChatController.java    # /api/chat
│   │       ├── NotesController.java   # /api/notes/*
│   │       ├── SettingsController.java # /api/settings/*
│   │       ├── SessionController.java  # /api/sessions/*
│   │       └── ...
│   └── frontend/           # React 前端
│       └── src/
│           ├── components/ # Header/Sidebar/ChatArea/SettingsDrawer/...
│           ├── pages/      # HomePage/NoteDetailPage/DashboardPage/LearningPage
│           └── api/        # API 客户端(client.ts + settings.ts)
├── agent.py                # 消费侧 LangGraph agent(命令行)
├── settings.json           # 多 Provider 配置(运行时可切换)
├── docs/                   # 设计文档 + 开发规范 + 踩坑记录
├── tests/                  # pytest(96 tests)
└── scripts/dev.py          # 统一开发命令(lint/type/test/coverage)
```

---

## 开发

```bash
# Python 端
python scripts/dev.py lint        # ruff 检查
python scripts/dev.py type        # mypy 类型检查
python scripts/dev.py test        # pytest(96 tests)

# Java 端
cd web/backend && mvn compile

# 前端
cd web/frontend && npx tsc --noEmit && npx vite build
```

提交前检查清单见 [开发规范](./docs/开发规范.md)。

---

## 与学习笔记的关系

这个项目是 **AI 学习工作区**「Agent 核心」线的工程落地(项目实战 P3):

| 笔记 | 在本项目哪里用到 |
|---|---|
| MCP 协议精读 | 三大原语、Host/Client/Server、双传输 |
| RAG / Embedding & 切块 | hybrid search、切块策略、embedding、溯源 |
| LangGraph | 消费侧 agent 的 ReAct 状态机 |

---

*项目状态:✅ Phase 3b 完成——Python MCP Server + Spring Boot 后端 + React 前端 + 多 Provider + 对话记录 · 2026-07-20*
