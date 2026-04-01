# mini-claude-code (Python版) — 完整三阶段构建规格


## 项目定位

构建一个用于学习 AI Agent 架构的简化版命令行工具，参照 Claude Code 架构理念从零实现。
不复制任何原始代码，cleanroom 设计。最终产出一个具备完整 agentic 能力的终端 AI 编程助手。

---

## 技术栈总览

| 层级 | 选型 | 说明 |
|------|------|------|
| 运行时 | Python 3.11+ | |
| 包管理 | `uv` | 替代 pip/poetry，速度快 |
| LLM 接入 | 抽象 `LLMProvider`，双实现 | `anthropic` SDK + `openai` SDK |
| Phase 1 UI | `rich` | 彩色终端输出，readline REPL |
| Phase 3 UI | `textual` | TUI 框架，类 React 组件模型 |
| 文件搜索 | `glob` / `pathspec` | 标准库 + gitignore 支持 |
| 异步运行时 | `asyncio` | 全链路 async |
| 类型检查 | `mypy` | strict 模式 |

---

## 最终目录结构

```
mini-claude-code/
├── src/
│   └── mini_claude/
│       ├── __init__.py
│       ├── main.py                  # 程序入口，组装依赖，选择 UI
│       ├── core/
│       │   ├── __init__.py
│       │   ├── types.py             # 全局类型定义（Message, ToolDef, ToolResult 等）
│       │   ├── query_engine.py      # ★ Agentic loop 核心
│       │   ├── context_manager.py   # 消息历史 + token 预算管理
│       │   └── permission.py        # 工具执行审批逻辑（Phase 2）
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── provider.py          # LLMProvider 抽象基类（ABC）
│       │   ├── anthropic_provider.py
│       │   └── openai_provider.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── registry.py          # 工具注册表
│       │   ├── base.py              # Tool 抽象基类
│       │   ├── bash.py
│       │   ├── read_file.py
│       │   ├── write_file.py
│       │   ├── glob_tool.py
│       │   └── patch.py             # Phase 2 新增：精准行级 diff patch
│       └── ui/
│           ├── __init__.py
│           ├── simple_repl.py       # Phase 1：rich + readline
│           └── tui/                 # Phase 3：Textual TUI
│               ├── __init__.py
│               ├── app.py           # Textual App 根组件
│               ├── chat_view.py     # 对话流组件
│               ├── tool_panel.py    # 工具执行状态面板
│               └── input_bar.py     # 底部输入栏
├── tests/
│   ├── test_query_engine.py
│   ├── test_tools.py
│   └── fixtures/
├── .env.example
├── pyproject.toml
└── README.md
```

---

## 类型系统（`src/mini_claude/core/types.py`）

**所有类型在此定义，其他模块从这里 import，禁止在各模块内部重复定义。**

```python
from typing import Literal, TypedDict, Union
from dataclasses import dataclass, field

# ── 消息系统 ──────────────────────────────────────────────

@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""

@dataclass
class ToolUseContent:
    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)

@dataclass
class ToolResultContent:
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: str = ""
    is_error: bool = False

MessageContent = Union[TextContent, ToolUseContent, ToolResultContent]

@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: list[MessageContent]

# ── 工具系统 ──────────────────────────────────────────────

@dataclass
class ToolResult:
    content: str
    is_error: bool = False

class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict  # JSON Schema

# ── LLM 流式输出 ──────────────────────────────────────────

@dataclass
class TextDelta:
    type: Literal["text_delta"] = "text_delta"
    text: str = ""

@dataclass
class ToolUseDelta:
    """收集完整的 tool_use block 后一次性发出"""
    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)

@dataclass
class StopSignal:
    type: Literal["stop"] = "stop"
    stop_reason: str = "end_turn"

LLMChunk = Union[TextDelta, ToolUseDelta, StopSignal]

# ── 权限系统（Phase 2）────────────────────────────────────

class PermissionLevel:
    AUTO = "auto"       # 自动批准
    ASK  = "ask"        # 询问用户
    DENY = "deny"       # 始终拒绝
```

---

## Phase 1：跑通 Agentic Loop

### 目标
用户输入自然语言任务，系统自主调用工具、推理、输出结果，支持多步骤串联。

### 1.1 LLMProvider 抽象层

**`src/mini_claude/llm/provider.py`**

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from mini_claude.core.types import Message, ToolDefinition, LLMChunk

class LLMProvider(ABC):
    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str = "",
    ) -> AsyncIterator[LLMChunk]:
        """流式调用 LLM，yield LLMChunk 直到 StopSignal"""
        ...
```

**`src/mini_claude/llm/anthropic_provider.py`** 关键实现要点：
- 使用 `anthropic.AsyncAnthropic`
- `stream()` 内部使用 `client.messages.stream()` context manager
- 将 Anthropic 的 `content_block_delta` 事件映射到 `TextDelta`
- 将完整的 `content_block_stop`（type=tool_use）映射到 `ToolUseDelta`
- input_json 通过 `input_json_delta` 事件累积，block stop 时一次性 parse

**`src/mini_claude/llm/openai_provider.py`** 关键实现要点：
- 使用 `openai.AsyncOpenAI`
- 通过 `client.chat.completions.create(stream=True)` 实现
- 将 `delta.content` 映射到 `TextDelta`
- 将 `delta.tool_calls` 累积后映射到 `ToolUseDelta`
- 注意：OpenAI tool_calls 的 arguments 是字符串，需要 `json.loads()`

---

### 1.2 Agentic Loop（`src/mini_claude/core/query_engine.py`）

**这是整个项目的学习核心，注释密度必须最高。**

```python
class QueryEngine:
    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
        max_iterations: int = 10,
    ): ...

    async def run(self, user_input: str) -> AsyncIterator[str]:
        """
        执行一轮 agentic loop，yield 文本片段供 UI 实时渲染。
        
        Loop 结构：
        
        while iteration < max_iterations:
            1. 调用 LLM，流式接收 chunks
            2. TextDelta → 直接 yield 给调用方（实时显示）
            3. ToolUseDelta → 收集到 pending_tool_calls[]
            4. StopSignal：
               a. 若 pending_tool_calls 为空 → break，对话结束
               b. 若有 pending_tool_calls：
                  - 并发执行所有工具（asyncio.gather）
                  - 将 assistant message + 所有 tool_result 追加到 context
                  - iteration += 1，继续 loop
        """
```

**并发执行工具的关键细节：**
```python
# 单次 LLM 响应可能包含多个 tool_use，必须全部执行后再继续
# 使用 asyncio.gather 并发执行，减少等待时间
results = await asyncio.gather(
    *[self._execute_tool(tc) for tc in pending_tool_calls],
    return_exceptions=True  # 任一工具失败不影响其他工具
)
```

**工具执行错误处理：**
```python
async def _execute_tool(self, tool_call: ToolUseDelta) -> ToolResultContent:
    # 错误必须作为 tool_result 返回给模型，不允许向上抛出
    # 让模型有机会自行纠错或向用户说明情况
    try:
        result = await self.tool_registry.execute(tool_call.name, tool_call.input)
        return ToolResultContent(
            tool_use_id=tool_call.id,
            content=result.content,
            is_error=result.is_error,
        )
    except Exception as e:
        return ToolResultContent(
            tool_use_id=tool_call.id,
            content=f"Tool execution failed: {type(e).__name__}: {e}",
            is_error=True,
        )
```

---

### 1.3 工具实现

**`src/mini_claude/tools/base.py`**

```python
from abc import ABC, abstractmethod
from mini_claude.core.types import ToolResult, ToolDefinition

class Tool(ABC):
    name: str
    description: str

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """返回传递给 LLM 的工具描述（含 JSON Schema）"""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...
```

**`bash.py`** 实现要点：
- 使用 `asyncio.create_subprocess_shell`，非阻塞
- `timeout=30`，超时后 `process.kill()` 并返回错误
- 同时捕获 `stdout` 和 `stderr`，合并返回
- 路径安全检查：通过 `Path(cwd).resolve()` 确保不逃逸工作目录
- 输出超过 10KB 时截断，附加 `[output truncated]` 提示

**`read_file.py`** 实现要点：
- 路径必须在 `cwd` 内（resolve 后比较前缀）
- 文件超过 100KB 时只读取前 100KB，附加截断提示
- 自动检测并返回文件编码（优先 utf-8，fallback latin-1）
- 二进制文件（图片等）返回错误提示而非乱码

**`write_file.py`** 实现要点：
- `Path(path).parent.mkdir(parents=True, exist_ok=True)` 自动建目录
- 路径安全检查同 read_file
- 写入成功后返回 `f"Successfully wrote {len(content)} chars to {path}"`

**`glob_tool.py`** 实现要点：
- 使用标准库 `glob.glob(pattern, recursive=True)`
- 结果上限 200 条，超出时附加提示
- 自动过滤 `.git/`、`__pycache__/`、`node_modules/`、`*.pyc`

**`src/mini_claude/tools/registry.py`**

```python
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None: ...

    def get_definitions(self) -> list[ToolDefinition]:
        """供 LLMProvider 使用"""
        ...

    async def execute(self, name: str, input_: dict) -> ToolResult:
        """查找工具并执行，工具不存在时返回 is_error=True 的 ToolResult"""
        ...
```

---

### 1.4 Context Manager（简化版）

```python
class ContextManager:
    def __init__(self, system_prompt: str = ""):
        self.system_prompt = system_prompt
        self._messages: list[Message] = []
        self._approx_tokens: int = 0  # 粗略估算：字符数 // 4

    def add_user_message(self, text: str) -> None: ...
    def add_assistant_turn(
        self,
        text_parts: list[str],
        tool_uses: list[ToolUseDelta]
    ) -> None: ...
    def add_tool_results(self, results: list[ToolResultContent]) -> None: ...
    def get_messages(self) -> list[Message]: ...
    def clear(self) -> None: ...

    async def compress(self) -> None:
        """Phase 2 实现，Phase 1 为空函数"""
        pass
```

---

### 1.5 Simple REPL（`src/mini_claude/ui/simple_repl.py`）

使用 `rich` 库实现：
- `Console` 对象用于彩色输出
- `Prompt.ask()` 获取用户输入
- 流式文本用 `console.print()` with `end=""` 实时输出
- 工具调用打印格式：`[bold cyan][Tool][/] bash › ls -la`
- 工具结果打印格式：`[dim]✓ 23ms[/dim]`
- 支持命令：`/exit`、`/clear`（清空历史）、`/history`（显示当前 token 估算）
- 启动时打印 banner，显示 provider 和模型名

---

### Phase 1 验收标准

- [ ] **A**：`列出当前目录的所有 Python 文件` → 触发 glob/bash，返回列表
- [ ] **B**：`创建 hello.py，内容是打印 hello world` → write_file 执行，文件实际存在
- [ ] **C**：`读取 pyproject.toml 告诉我有哪些依赖` → read_file + 模型正确解析
- [ ] **D**：`用 python 运行 hello.py` → bash 执行，输出 hello world
- [ ] **E**：多步串联任务在一次对话中完成（创建→读取→修改→运行）
- [ ] **F**：切换 `LLM_PROVIDER=openai` 后，A-E 全部通过
- [ ] **G**：工具执行报错时，模型收到错误并尝试自我修正

---

## Phase 2：权限系统 + 上下文压缩

### 2.1 权限审批（`src/mini_claude/core/permission.py`）

**权限分级规则：**

```python
PERMISSION_RULES: dict[str, str] = {
    # 工具名 → 默认权限级别
    "read_file":  PermissionLevel.AUTO,   # 只读，自动批准
    "glob":       PermissionLevel.AUTO,   # 只读，自动批准
    "bash":       PermissionLevel.ASK,    # 执行命令，需确认
    "write_file": PermissionLevel.ASK,    # 写文件，需确认
    "patch":      PermissionLevel.ASK,    # 修改文件，需确认
}
```

**动态升级规则**（需在 `PermissionManager` 中实现）：
- bash 命令中包含 `rm`、`sudo`、`chmod`、`curl`、`wget`、`>` 重定向 → 升级为 ASK（即使默认为 AUTO）
- write_file 路径在 cwd 外 → 升级为 DENY

**审批流程：**
```
AUTO → 直接执行，打印 [Auto] tool_name: summary
ASK  → 打印工具名 + 完整参数，等待 y/n/always/never
       - y: 本次批准
       - n: 本次拒绝，返回拒绝信息给模型
       - always: 本 session 内该工具自动批准
       - never: 本 session 内该工具自动拒绝
DENY → 直接拒绝，返回拒绝信息给模型
```

**QueryEngine 集成：** 在 `_execute_tool` 中，执行工具前先调用 `PermissionManager.check(tool_name, input)`。

---

### 2.2 Patch 工具（`src/mini_claude/tools/patch.py`）

比 write_file 更精准的文件修改工具，避免每次重写整个文件。

```python
# 工具输入 schema：
{
    "file_path": str,
    "old_str": str,   # 必须在文件中唯一存在
    "new_str": str,   # 替换内容，空字符串表示删除
}

# 实现要点：
# 1. 读取文件内容
# 2. 检查 old_str 出现次数，不等于 1 时返回错误（避免错误替换）
# 3. 替换后写回
# 4. 返回 diff 摘要（显示修改了哪几行）
```

---

### 2.3 上下文压缩（`src/mini_claude/core/context_manager.py`）

**触发条件：** 估算 token 数超过 `max_tokens * 0.75`（默认阈值 ~150k tokens）

**压缩策略：**
```
保留：
  - system prompt（始终保留）
  - 最近 6 轮对话（user + assistant + tool_results）
  - 第一轮对话（保留原始任务上下文）

压缩：
  - 中间部分调用一次 LLM 生成摘要
  - 摘要作为 user message 插入，角色标注为 [Context Summary]

压缩后打印：[dim]Context compressed: 180k → 42k tokens[/dim]
```

**实现接口：**
```python
async def maybe_compress(self, provider: LLMProvider) -> bool:
    """如果需要压缩则执行，返回是否发生了压缩"""
    if self._approx_tokens < self.compression_threshold:
        return False
    await self.compress(provider)
    return True
```

**QueryEngine 集成：** 每轮 loop 开始前调用 `context_manager.maybe_compress(provider)`。

---

### Phase 2 验收标准

- [ ] **A**：执行危险 bash 命令（如 `rm test.txt`）时弹出确认提示
- [ ] **B**：输入 `always` 后，同一工具后续自动批准
- [ ] **C**：patch 工具能精准修改文件中一行，不影响其他内容
- [ ] **D**：old_str 在文件中出现多次时，patch 返回错误而非静默错误替换
- [ ] **E**：对话超过压缩阈值后，上下文被压缩，对话仍可继续（模型不失忆关键信息）
- [ ] **F**：`/history` 命令显示压缩前后的 token 估算对比

---

## Phase 3：Textual TUI

### 3.1 整体布局

```
┌─────────────────────────────────────────────┐
│  mini-claude-code          [anthropic/sonnet]│  ← Header
├───────────────────────────┬─────────────────┤
│                           │  Tool Calls      │
│    Chat View              │  ─────────────  │
│                           │  ✓ read_file    │
│    [用户消息气泡]          │    src/main.py  │
│                           │    23ms         │
│    [助手流式输出]          │                 │
│                           │  ⟳ bash (running│
│                           │    pytest       │
│                           │                 │
├───────────────────────────┴─────────────────┤
│  > █                          [↑ history]   │  ← Input Bar
└─────────────────────────────────────────────┘
```

### 3.2 组件设计

**`src/mini_claude/ui/tui/app.py`（Textual App）**

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.containers import Horizontal

class MiniClaudeApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear_history", "Clear"),
        ("f1", "toggle_tool_panel", "Tools"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ChatView(id="chat")
            yield ToolPanel(id="tools")
        yield InputBar(id="input")
        yield Footer()
```

**`src/mini_claude/ui/tui/chat_view.py`**
- 继承 `textual.widgets.RichLog`
- 用户消息：右对齐，`[bold green]You[/]` 前缀
- 助手消息：左对齐，`[bold blue]Claude[/]` 前缀，支持 Markdown 渲染
- 流式输出：通过 `reactive` 属性驱动，每个 TextDelta 触发局部更新
- 错误消息：`[bold red]Error[/]` 前缀

**`src/mini_claude/ui/tui/tool_panel.py`**
- 继承 `textual.widgets.ListView`
- 每个工具调用显示为一个 `ListItem`：
  - 运行中：`⟳ tool_name` + spinner（使用 `textual.widgets.LoadingIndicator`）
  - 成功：`✓ tool_name` + 耗时（绿色）
  - 失败：`✗ tool_name` + 错误摘要（红色）
- 点击某条可展开查看完整输入/输出

**`src/mini_claude/ui/tui/input_bar.py`**
- 继承 `textual.widgets.Input`
- `Enter` 提交，`Shift+Enter` 换行
- `↑/↓` 方向键浏览历史输入（维护本地 history 列表）
- 模型生成中禁用输入（`self.disabled = True`），完成后恢复

**异步集成：**
```python
# QueryEngine.run() 是 AsyncIterator
# 在 Textual 中通过 worker 运行：
async def on_input_submitted(self, event: Input.Submitted) -> None:
    self.run_worker(self._stream_response(event.value))

async def _stream_response(self, user_input: str) -> None:
    async for chunk in self.query_engine.run(user_input):
        self.query_one("#chat", ChatView).append_text(chunk)
```

---

### 3.3 样式（`app.tcss`）

```css
Screen {
    background: #0d1117;
}

ChatView {
    width: 1fr;
    border-right: solid #30363d;
    padding: 1 2;
}

ToolPanel {
    width: 35;
    background: #161b22;
    padding: 1;
}

InputBar {
    height: 3;
    border-top: solid #30363d;
    background: #0d1117;
}

Header {
    background: #161b22;
    color: #58a6ff;
}
```

---

### Phase 3 验收标准

- [ ] **A**：TUI 正常启动，三栏布局正确渲染
- [ ] **B**：流式文本在 ChatView 中实时追加，无卡顿
- [ ] **C**：工具执行期间 ToolPanel 显示 spinner，完成后更新为耗时
- [ ] **D**：点击 ToolPanel 中的工具条目，展开完整参数和输出
- [ ] **E**：`Ctrl+L` 清空对话历史，界面同步清空
- [ ] **F**：Phase 2 的权限审批弹出对话框（`textual.widgets.ModalScreen`）而非 input prompt
- [ ] **G**：`--simple` 启动参数切换回 Phase 1 的 rich REPL（保留降级路径）

---

## 环境变量规范

```bash
# .env.example

# 选择 provider：anthropic 或 openai
LLM_PROVIDER=anthropic

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5-20251001

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# 行为控制
MAX_ITERATIONS=10          # agentic loop 最大轮次
COMPRESSION_THRESHOLD=150000  # token 压缩触发阈值（字符估算）
WORK_DIR=.                 # 工具操作的根目录，默认当前目录
UI_MODE=tui                # tui 或 simple
```

---

## pyproject.toml

```toml
[project]
name = "mini-claude-code"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.39.0",
    "openai>=1.0.0",
    "rich>=13.0.0",
    "textual>=0.80.0",
    "python-dotenv>=1.0.0",
    "pathspec>=0.12.0",
]

[project.optional-dependencies]
dev = [
    "mypy>=1.0.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[project.scripts]
mini-claude = "mini_claude.main:main"

[tool.mypy]
strict = true
```

---

## 实现顺序（严格遵守）

```
Step 1  src/mini_claude/core/types.py
        — 先把所有类型定好，后续不允许在模块内定义重复类型

Step 2  src/mini_claude/llm/provider.py
        src/mini_claude/llm/anthropic_provider.py
        — 先跑通单次无工具调用

Step 3  src/mini_claude/tools/base.py
        src/mini_claude/tools/registry.py
        src/mini_claude/tools/bash.py
        — 最小工具集，手动测试 bash 工具

Step 4  src/mini_claude/core/context_manager.py  (Phase 1 版本)
        src/mini_claude/core/query_engine.py
        — 用 bash 工具联调完整 agentic loop

Step 5  src/mini_claude/tools/read_file.py
        src/mini_claude/tools/write_file.py
        src/mini_claude/tools/glob_tool.py
        — 补全工具，验收 Phase 1

Step 6  src/mini_claude/ui/simple_repl.py
        src/mini_claude/main.py
        — 组装 Phase 1 完整入口

Step 7  src/mini_claude/llm/openai_provider.py
        — 复用已有 loop，测试 OpenAI 兼容性

Step 8  src/mini_claude/core/permission.py
        src/mini_claude/tools/patch.py
        — Phase 2 权限系统

Step 9  src/mini_claude/core/context_manager.py  (完整版，含压缩)
        — Phase 2 上下文压缩

Step 10 src/mini_claude/ui/tui/
        — Phase 3 TUI，最后实现
```

---

## 注释规范

`query_engine.py` 每个 loop 阶段必须有块注释，示例：

```python
# ── Step 2: 收集本轮所有 tool_use ──────────────────────────────────
# 单次 LLM 响应可能包含多个 tool_use block。
# 必须等所有工具执行完毕，把全部 tool_result 一次性追加到 messages，
# 再发起下一轮 LLM 调用。
#
# 原因（Anthropic API 约束）：
#   assistant message 中的每个 tool_use 必须有对应的 tool_result，
#   且必须在下一个 user message 中一次性提供，不能分批发送。
#
# 对于 OpenAI：tool_calls 在 assistant message 中，
#   tool_result 通过 role="tool" 的 message 提供，逻辑相同。
# ──────────────────────────────────────────────────────────────────
```

---

## 不做的事（明确边界）

- ❌ 多 Agent 协调（coordinator 模式）
- ❌ 后台 daemon / autoDream
- ❌ IDE bridge（VS Code / JetBrains 插件）
- ❌ 遥测与分析
- ❌ 持久化会话 / 跨进程记忆
- ❌ 语音交互
- ❌ 图片/多模态输入（工具层面）
