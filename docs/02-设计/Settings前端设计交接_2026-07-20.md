# Settings 页面 · 前端设计交接

> 给设计 Settings 页面的 AI —— 多 Provider 配置的 API、数据结构、修改范围。
> 2026-07-20

---

## 1. 背景

notes-mcp 现在支持**三种 AI Provider**:

| Provider | 说明 | 适用场景 |
|---|---|---|
| **Ollama** | 本地模型(默认) | 免费、离线、隐私,需安装 Ollama |
| **OpenAI** | OpenAI 官方 API | GPT-4o / GPT-4o-mini |
| **自定义** | 任意 OpenAI 兼容端点 | DeepSeek / Groq / vLLM / LM Studio / 硅基流动 等 |

用户通过 `settings.json` 切换 Provider,配置文件位于项目根:
```
D:\Learn\AI\项目\notes-mcp\settings.json
```

---

## 2. Settings API

### 2.1 `GET /api/settings` — 获取完整配置

返回当前所有 Provider 配置(**API 密钥已脱敏**):

```json
{
  "notesDir": "d:/Learn/AI/笔记;d:/Learn/AI/项目/rag-agent/docs",
  "activeProvider": "ollama",
  "ollama": {
    "name": "Ollama 本地",
    "baseUrl": "http://127.0.0.1:11434",
    "apiKey": "",
    "selectedModel": "qwen3:8b",
    "hasKey": false
  },
  "openai": {
    "name": "OpenAI",
    "baseUrl": "https://api.openai.com/v1",
    "apiKey": "",
    "selectedModel": "gpt-4o-mini",
    "hasKey": false
  },
  "custom": {
    "name": "自定义",
    "baseUrl": "",
    "apiKey": "",
    "selectedModel": "",
    "hasKey": false
  }
}
```

> **关键**: `apiKey` 字段只显示后 4 位(如 `****b1a2`),不存在时为空字符串。`hasKey` 表示是否已配置了有效密钥。
>
> **`notesDir`**: 笔记目录路径,支持 `;` 分号分隔多目录(如 `d:/笔记;d:/项目/docs`)。

### 2.2 `PUT /api/settings` — 更新配置

**更新 Provider 配置**:

```json
// 请求
{
  "provider": "openai",
  "name": "OpenAI",
  "baseUrl": "https://api.openai.com/v1",
  "apiKey": "sk-proj-xxxxxxxxxxxxx",
  "selectedModel": "gpt-4o"
}

// 响应
{
  "message": "配置已保存",
  "provider": "openai"
}
```

**更新笔记目录**:

```json
// 请求
{
  "notesDir": "d:/Learn/AI/笔记;d:/Learn/AI/项目/rag-agent/docs"
}

// 响应
{
  "notesDir": "d:/Learn/AI/笔记;d:/Learn/AI/项目/rag-agent/docs",
  "requiresRestart": true,
  "message": "笔记目录已保存。修改笔记目录需重启后端才能生效"
}
```

> **注意**:
> - 如果 `apiKey` 以 `****` 开头(前端没改密钥),后端保留原值不覆盖。用户输入新密钥时才更新。
> - 修改 `notesDir` 后 `requiresRestart: true`——**前端应提示用户重启后端**。
> - `notesDir` 支持 `;` 分号分隔多个目录。

### 2.3 `POST /api/provider/select` — 切换 Provider

```json
// 请求
{ "provider": "ollama" }

// 响应
{
  "activeProvider": "ollama",
  "message": "已切换为 ollama"
}
```

`provider` 取值: `"ollama"` | `"openai"` | `"custom"`

### 2.4 `GET /api/models` — 获取可用模型列表

```json
{
  "provider": "ollama",
  "current": "qwen3:8b",
  "models": [
    { "name": "qwen3:8b", "size": "5.2 GB" },
    { "name": "qwen2.5-coder:3b", "size": "1.9 GB" },
    { "name": "bge-m3:latest", "size": "1.2 GB" }
  ]
}
```

- Ollama provider: `size` 显示模型文件大小
- OpenAI / Custom provider: 字段略不同(无 size,有 `ownedBy`)
- 当前选中的模型在 `current` 字段

### 2.5 `POST /api/models/select` — 切换模型

```json
// 请求
{ "model": "qwen2.5-coder:3b" }

// 响应
{
  "current": "qwen2.5-coder:3b",
  "message": "模型已切换"
}
```

### 2.6 `POST /api/models/refresh` — 刷新模型列表

重新从当前 Provider 拉取模型列表(Ollama 调 `/api/tags`, OpenAI 调 `/v1/models`)。

```json
// 响应(与 GET /api/models 格式相同)
{
  "provider": "ollama",
  "current": "qwen3:8b",
  "models": [...]
}
```

---

## 3. 数据结构 (TypeScript)

```typescript
// Provider 类型
type ProviderType = 'ollama' | 'openai' | 'custom';

// 单个 Provider 配置
interface ProviderConfig {
  name: string;           // 显示名称
  baseUrl: string;        // API 端点
  apiKey: string;         // API 密钥(脱敏后: "****xxxx")
  selectedModel: string;  // 当前选中的模型
  hasKey: boolean;        // 是否已配置密钥
}

// Settings 完整结构
interface Settings {
  notesDir: string;          // 笔记目录(; 分隔多目录)
  activeProvider: ProviderType;
  ollama: ProviderConfig;
  openai: ProviderConfig;
  custom: ProviderConfig;
}

// 模型列表响应
interface ModelsResponse {
  provider: ProviderType;
  current: string;              // 当前选中的模型名
  models: { name: string; size?: string; ownedBy?: string }[];
}
```

---

## 4. 需要设计的页面

### 4.1 设置入口

建议在 **Header 右侧**增加一个齿轮图标 ⚙️,点击进入设置页面或弹出设置抽屉(Drawer)。

### 4.2 设置页/抽屉内容

#### Tab 1: 笔记目录
- 输入框:笔记文件夹路径,支持 `;` 分隔多目录
- 默认值: `d:/Learn/AI/笔记`
- 提示: "支持多个目录,用分号 `;` 分隔"
- 保存后显示 ⚠️ 警告: "修改笔记目录需重启后端才能生效"
- "打开文件夹"按钮(可选,调系统文件选择器)

#### Tab 2: Provider 选择
- 三个卡片/标签切换: 🖥️ Ollama 本地 | ☁️ OpenAI | 🔧 自定义
- 当前选中的 Provider 高亮(紫色边框 + 对勾)
- 切换时调用 `POST /api/provider/select`

#### Tab 3: Provider 配置
- **Ollama**: baseUrl 输入框(默认 `http://127.0.0.1:11434`),无需 API Key
- **OpenAI**: baseUrl 输入框 + API Key 输入框(password 类型,placeholder 显示脱敏值)
- **自定义**: name 输入框 + baseUrl 输入框 + API Key 输入框
- 保存按钮 → `PUT /api/settings`

#### 模型选择器
- 下拉框或卡片列表,显示当前 Provider 可用模型
- 选中后调用 `POST /api/models/select`
- "刷新"按钮 → `POST /api/models/refresh`
- Ollama 模型显示文件大小,OpenAI 模型显示模型 ID

#### 状态提示
- Provider 切换后提示"已切换为 XXX"
- API Key 未配置时显示警告: "⚠️ 未配置 API Key,无法使用此 Provider"
- 模型列表加载失败时显示错误提示

---

## 5. 修改范围

### 需要新增的文件

| 文件 | 说明 |
|---|---|
| `src/api/settings.ts` | Settings 相关 API 调用(7 个端点的方法封装) |
| `src/pages/SettingsPage.tsx` | 设置页面(或 Drawer 组件) |

### 需要修改的文件

| 文件 | 修改内容 |
|---|---|
| `src/App.tsx` | 新增 `/settings` 路由 |
| `src/components/Header.tsx` | 新增模型选择器(显示当前模型 + 下拉切换) + 设置入口图标 |
| `src/components/ChatArea.tsx` | 对话时可选:显示当前使用的 Provider + Model(如 "🤖 Ollama / qwen3:8b") |

### 不需要修改的部分
- 后端无需改动(所有 Settings API 已就绪)
- Sidebar / ChatInput / InfoPanel 无需改动
- 其他页面无需改动

---

## 6. UI 建议

- 设置页建议用 **Drawer(抽屉)** 从右侧滑出,而不是独立页面(不打断对话)
- 模型选择器放在 Header 中间位置(替换当前的"我的 AI 学习库"文字),显示为 `🖥️ Ollama / qwen3:8b ▼`
- API Key 输入框用 `type="password"`,显示/隐藏切换
- 三个 Provider 用卡片式选择,每个卡片显示图标 + 名称 + 一句话描述

---

## 7. 现有文件参考

```
web/frontend/src/
├── api/client.ts           # 现有 API 客户端(5 个端点)—— 新增 settings.ts 放在同目录
├── components/Header.tsx   # 顶部栏 —— 需要改
├── components/ChatArea.tsx # 聊天区 —— 可选改动
├── pages/                  # 页面目录 —— 新增 SettingsPage.tsx
└── types/index.ts          # 类型定义 —— 可能需要扩展
```

后端 Settings 相关代码:
```
web/backend/src/main/java/com/notesmcp/backend/
├── SettingsData.java       # settings.json 数据结构
├── SettingsService.java    # 读写 + 模型拉取
├── SettingsController.java # REST API(7 个端点,含 notesDir)
└── ProviderRouter.java     # 根据 Provider 路由对话
```
