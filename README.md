# LocalNexus PC

**LocalNexus PC** 是一款功能强大的本地 AI 聊天桌面应用，支持 OpenAI 兼容 API、插件扩展、MCP 工具服务器集成、长期记忆与语音合成（TTS）。它提供了完整的对话管理、流式响应、工具调用和可定制的 AI 提示词系统，适合作为个人 AI 助手或开发平台。

## ✨ 主要特性

- **多对话管理**：创建、删除、重命名对话，自动保存聊天记录。
- **流式聊天**：实时显示 AI 回复，支持 Markdown 渲染和代码高亮。
- **工具调用（Function Calling）**：
  - 内置记忆查询工具
  - 本地插件暴露的工具（如时间戳、文本转换）
  - 远程 MCP 工具服务器（通过 SSE 协议）
- **插件系统**：Python 插件可处理用户消息、AI 响应，并提供自定义工具。
- **MCP 工具服务器**：支持多个 MCP 服务器配置，动态加载工具，自动重连。
- **长期记忆系统**（基于 [LocalNexus](https://github.com/cjz-wr/LocalNexus) 的记忆管理方案）：
  - 基于 LLM 的对话提炼，生成结构化记忆（树形存储）
  - 使用 LanceDB + 向量检索，支持语义查询
  - 关联原始对话，实现跨会话记忆回溯
- **TTS 语音合成**：基于 Edge-TTS，流式生成并播放语音，支持多参数调节。
- **系统提示词管理**：可创建、编辑、切换多种系统提示词，即时生效。
- **完整的设置界面**：管理 API 密钥、模型参数、MCP 服务器、TTS、记忆精炼模型等。
- **右侧提示词侧边栏**：快速选择/编辑 AI 提示词。
- **响应式 UI**：侧边栏可收起，支持暗色/亮色主题（自适应系统）。

## 🧰 技术栈

### 前端
- **Electron**（主进程提供后端通信）
- HTML5 / CSS3（Flex 布局，自定义样式）
- JavaScript（ES6+）
- [Marked](https://marked.js.org/) + [Highlight.js](https://highlightjs.org/)（Markdown 渲染与代码高亮）

### 后端
- **Python 3.10+**
- **FastAPI** + **Uvicorn**（Web 框架）
- **WebSockets**（流式聊天）
- **OpenAI SDK**（兼容 OpenAI API）
- **MCP SDK**（Model Context Protocol 客户端）
- **LanceDB**（向量数据库，记忆存储）
- **Sentence‑Transformers**（BAAI/bge‑m3 中文嵌入模型）
- **SQLite**（对话、插件状态、工具状态、提示词存储）
- **Edge‑TTS**（语音合成）
- **Pygame**（本地音频播放）

> 长期记忆系统的核心实现（`RefineMemory.py`、`treeMemoryStore.py`）参考并整合了 [LocalNexus](https://github.com/cjz-wr/LocalNexus) 项目的设计。

## 📦 安装与运行

### 环境要求
- Node.js 16+（用于 Electron 前端）
- Python 3.10+（后端）
- pip（Python 包管理器）

### 1. 克隆仓库
```bash
git clone https://github.com/yourusername/LocalNexus-PC.git
cd LocalNexus-PC
```

### 2. 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

### 3. 启动后端服务
```bash
python main.py
```
后端默认运行在 `http://localhost:8765`，可通过环境变量 `BACKEND_PORT` 修改。

### 4. 安装前端依赖（Electron 应用）
在项目根目录（包含 `package.json` 的目录）执行：
```bash
npm install
```

### 5. 启动 Electron 应用
```bash
npm start
```

> 首次启动时，后端端口会自动检测（通过 `check_port.py`），无需手动配置。

## ⚙️ 配置说明

### OpenAI API 配置
打开应用设置（侧边栏底部齿轮图标），填写：
- **API Key**：你的 OpenAI API 密钥（或兼容服务的密钥）
- **Base URL**：默认为 `https://api.openai.com/v1`，可改为其他兼容端点
- **模型**：如 `gpt-3.5-turbo`、`gpt-4` 等
- **Max Tokens**、**Temperature**：控制回复长度与随机性

### MCP 工具服务器
在“设置 → MCP 工具服务器管理”中添加多个 MCP 配置：
- **配置名称**：自定义标识
- **服务器地址**：MCP 服务器的 SSE 端点（例如 `http://localhost:8080`）
- **模型名称**：传递给 MCP 服务器的模型标识（可选）
- **认证 Token**：Bearer Token（可选）

启用后，系统会自动拉取工具并可用于 Function Calling。

### 长期记忆
- **启用长期记忆**：开启后 AI 会定期提炼对话存入记忆库
- **精炼模型**：用于提炼记忆的 LLM（默认使用聊天模型，可单独配置）
- **触发百分比**：新消息 token 达到模型最大 token 的该比例时触发记忆提炼
- **滑动窗口清理**：总 token 超过阈值时自动删除最早的历史消息

### TTS 语音
- 启用后，AI 回复会实时合成语音并播放
- 可调节语音、语速、音调、音量

## 🔌 插件开发

插件位于 `backend/plugins/` 目录，每个插件是一个 Python 文件，需包含以下内容：

```python
# 插件元信息
info = {
    'name': 'my_plugin',
    'version': '1.0.0',
    'description': '插件描述'
}

# 可选：提供工具定义
def get_tools():
    return [{
        'name': 'my_tool',
        'description': '工具描述',
        'parameters': {...}   # JSON Schema
    }]

# 可选：执行工具
def execute_tool(tool_name: str, arguments: dict):
    # 返回字符串或可序列化对象
    return result

# 可选：处理用户消息
def on_user_message(message: str, context: dict) -> str:
    return modified_message

# 可选：处理 AI 响应
def on_ai_response(response: str, context: dict) -> str:
    return modified_response
```

插件启用/禁用可通过“设置 → 插件”管理。

## 📁 项目结构

```
LocalNexus-PC/
├── backend/                  # Python 后端
│   ├── main.py               # 入口
│   ├── routes.py             # FastAPI 路由
│   ├── websocket_handler.py  # WebSocket 聊天处理
│   ├── ai_clients.py         # OpenAI 客户端封装
│   ├── tool_manager.py       # 工具管理器（MCP + 插件）
│   ├── plugin_manager.py     # 插件加载与管理
│   ├── tts.py                # TTS 工作线程
│   ├── RefineMemory.py       # 记忆提炼模块（基于 LocalNexus）
│   ├── treeMemoryStore.py    # 树形记忆存储（基于 LocalNexus）
│   ├── builtin_tools.py      # 内置工具（记忆查询）
│   ├── config.py             # 配置与数据库初始化
│   ├── models.py             # Pydantic 模型
│   ├── plugins/              # 用户插件目录
│   │   ├── timestamp_plugin.py
│   │   └── uppercase_plugin.py
│   └── requirements.txt
├── page/                     # Electron 前端（渲染进程）
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── main.js               # Electron 主进程（如适用）
├── storage/                  # 记忆数据库存储（自动创建）
├── hf_cache/                 # HuggingFace 模型缓存
└── README.md
```

## 🚀 使用指南

1. **新建对话**：点击侧边栏“+”按钮。
2. **发送消息**：在底部输入框键入内容，按 Enter 发送（Shift+Enter 换行）。
3. **工具调用**：当 AI 需要调用工具时，界面会显示工具状态（运行中/完成/失败），并自动整合结果继续对话。
4. **切换提示词**：右侧侧边栏可查看、新建、编辑系统提示词，点击“✔”激活当前提示词。
5. **查看记忆**：设置中开启记忆后，AI 会自动学习并可在后续对话中引用历史记忆。
6. **语音播放**：启用 TTS 后，AI 回复将自动朗读（需系统音频设备正常）。

## ❓ 常见问题

**Q：后端启动失败，提示端口被占用？**  
A：修改 `backend/backend_port.json` 中的端口，或设置环境变量 `BACKEND_PORT=xxxx`。

**Q：MCP 服务器连接不上？**  
A：检查服务器地址是否正确，是否支持 SSE 协议。可在设置中测试连接（目前未直接提供，可通过工具调用日志排查）。

**Q：记忆提炼不生效？**  
A：确保已启用长期记忆，并且已配置有效的 OpenAI API Key（或精炼模型 API Key）。提炼会在新消息累计达到触发阈值后自动执行。

**Q：TTS 没有声音？**  
A：确认已安装 `pygame`，并且系统音频设备正常。可在设置中测试（目前无单独测试按钮，可尝试发送一条短消息触发）。

**Q：插件加载失败？**  
A：检查插件文件语法，确保定义了 `info` 字典。插件错误会打印在后端控制台。

## 📄 许可证

本项目采用 Apache 2.0 许可证。详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [OpenAI](https://openai.com/) – 提供强大的语言模型 API
- [Model Context Protocol](https://modelcontextprotocol.io/) – 工具服务器标准
- [LanceDB](https://lancedb.com/) – 向量数据库
- [Edge-TTS](https://github.com/rany2/edge-tts) – 免费的 TTS 服务
- [LocalNexus](https://github.com/cjz-wr/LocalNexus) – 提供记忆管理系统的基础架构与设计灵感
- 所有贡献者和开源社区

---

**LocalNexus PC** 致力于打造一个本地优先、可扩展的 AI 伴侣。欢迎提交 Issue 和 Pull Request！
```
