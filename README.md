<p align="center">
	<img src="https://raw.githubusercontent.com/li-dashan/mini-claude-code/main/assets/logo.svg" width="136" alt="mini-claude-code logo" />
</p>

<h1 align="center">mini-claude-code</h1>

<p align="center">
	一个用于学习 AI Agent 架构的 Python 项目。<br/>
	目标是用最小可读实现复刻「带工具调用的终端助手」核心流程。
</p>

<p align="center">
	<a href="https://pypi.org/project/mini-claude-code/"><img alt="PyPI" src="https://img.shields.io/pypi/v/mini-claude-code" /></a>
	<a href="https://github.com/li-dashan/mini-claude-code/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/li-dashan/mini-claude-code/ci.yml?branch=main&label=tests" /></a>
	<a href="https://github.com/li-dashan/mini-claude-code/releases"><img alt="Release" src="https://img.shields.io/github/v/release/li-dashan/mini-claude-code?display_name=tag" /></a>
	<a href="https://github.com/li-dashan/mini-claude-code/commits/main"><img alt="Last Commit" src="https://img.shields.io/github/last-commit/li-dashan/mini-claude-code/main" /></a>
	<a href="https://github.com/li-dashan/mini-claude-code/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/li-dashan/mini-claude-code" /></a>
	<img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" />
	<img alt="UI" src="https://img.shields.io/badge/UI-Rich%20%2B%20Textual-1E293B" />
</p>

## 界面预览


<p align="center">
	<img src="https://raw.githubusercontent.com/li-dashan/mini-claude-code/main/assets/tui-screenshot-placeholder.png" alt="mini-claude TUI screenshot" width="100%" />
</p>

## 特性亮点

- 双 Provider：支持 Anthropic / OpenAI，统一走 `LLMProvider` 抽象层
- OpenAI 兼容平台接入：支持 `OPENAI_BASE_URL`（如 147api）
- Agentic Loop：流式输出 + 工具调用 + 多轮迭代
- 多工具系统：`bash` / `read_file` / `write_file` / `glob`
- 两套终端体验：`simple`（Rich REPL）与 `tui`（Textual 界面）
- Buddy 电子宠物：多角色设定（外表/特性/故事/数值），按 username+hostname 永久分配，不可切换
- 思考动画 + 工具反馈：thinking 时动态表情，工具调用成功/失败会影响心情与信任值
- 运行时配置管理：`/show-config`、`/set-config`，并自动持久化到 `.env`
- 工具可视化与手动调用：`/tools`、`/tool <name> <json-args>`
- TUI 交互增强：Tab 命令补全、配置键补全、↑↓ 输入历史
- 可读性导向：代码结构清晰，适合学习和二次改造

## 快速开始

### 1. 安装

方式 1（推荐，uv）：

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

方式 2（pip）：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

至少配置以下变量之一：

- `ANTHROPIC_API_KEY`（当 `LLM_PROVIDER=anthropic`）
- `OPENAI_API_KEY`（当 `LLM_PROVIDER=openai`）

常用配置：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-sonnet-4-5-20251022
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
# OPENAI_BASE_URL=https://api.147ai.cn/v1
MAX_ITERATIONS=10
WORK_DIR=.
UI_MODE=simple
```

说明：

- `UI_MODE=tui` 时启动 Textual TUI
- 默认 `UI_MODE=simple` 为 Rich REPL
- 使用 147api 等聚合平台时：
	- `LLM_PROVIDER=openai`
	- `OPENAI_API_KEY=<平台 key>`
	- `OPENAI_BASE_URL=<平台 OpenAI 兼容 base url>`（通常带 `/v1`）

### 2.1 配置文件查找优先级

`mini-claude` 启动时会按以下顺序加载环境变量（命中即停止）：

1. `MINI_CLAUDE_ENV_FILE` 指定的文件
2. 当前工作目录向上查找 `.env`
3. 包/项目根目录附近的 `.env`
4. 用户级配置：`~/.config/mini-claude/.env`、`~/.mini-claude/.env`
5. 当前工作目录向上查找 `.env.example`
6. 包/项目根目录附近的 `.env.example`

这意味着你可以在任意路径执行 `mini-claude`，并通过 `MINI_CLAUDE_ENV_FILE` 精确指定配置文件。

### 3. 运行

```bash
mini-claude
```

或：

```bash
python -m mini_claude.main
```

## 交互命令

- `/exit`：退出
- `/clear`：清空上下文历史
- `/history`：显示当前上下文估算 token 数
- `/buddy`：查看 buddy 当前状态与名册
- `/profile`：查看 buddy 完整介绍页（含属性数值可视化）
- `/pet`：抚摸 buddy，提升信任值
- `/feed`：投喂 buddy，恢复能量
- `/show-config [KEY]`：查看全部或单个运行时配置
- `/set-config <KEY> <VALUE>`：修改配置，并写回 `.env`
- `/tools`：查看已注册工具列表
- `/tool <NAME> <JSON_ARGS>`：手动调用工具（调试/教学很有用）

示例：

```bash
/show-config
/set-config MAX_ITERATIONS 20
/tools
/tool bash {"command":"ls -la"}
```

支持的运行时配置键：

- `LLM_PROVIDER`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `MAX_ITERATIONS`
- `WORK_DIR`
- `system_prompt`

## Agentic Loop 核心

`QueryEngine.run()` 关键流程：

1. 记录用户输入到上下文
2. 流式调用 LLM 并实时输出文本
3. 收集工具调用请求
4. 并发执行工具并写回结果
5. 在 `max_iterations` 内循环，直到模型结束当前回合

该结构支持一个回合内的「思考 -> 调工具 -> 再思考」迭代。

## 项目结构

```text
src/mini_claude/
	main.py                  # 程序入口，组装 Provider / Tool / UI
	core/
		config.py              # 运行时配置管理（show/set-config + .env 持久化）
		context_manager.py     # 上下文与消息管理
		query_engine.py        # Agentic Loop 核心
		types.py               # 全局类型定义
	llm/
		provider.py            # LLM 抽象接口
		anthropic_provider.py  # Anthropic 实现
		openai_provider.py     # OpenAI/OpenAI-compatible 实现
	tools/
		base.py                # Tool 抽象基类
		registry.py            # 工具注册与调度
		bash.py                # Bash 执行
		read_file.py           # 文件读取
		write_file.py          # 文件写入
		glob_tool.py           # Glob 搜索
	ui/
		buddy.py               # Buddy 电子宠物系统
		simple_repl.py         # Rich 终端 REPL
		tui/
			app.py               # Textual TUI
```

## 开发

安装开发依赖：

```bash
pip install -e .[dev]
```

类型检查：

```bash
mypy src
```

测试：

```bash
pytest
```

## 发布流程（GitHub + PyPI）

当前项目已配置：

- `Release Please`：自动生成 release PR / tag / GitHub Release
- 自动发布 PyPI：在 release 创建后构建并上传
- 手动兜底发布：`Release Publish` workflow（`workflow_dispatch`）

建议发布步骤：

1. 按 Conventional Commits 提交（`feat:` / `fix:` 等）
2. 合并 release-please 生成的 release PR
3. 等待 GitHub Actions 完成发布
4. 在 PyPI 页面确认新版本可见

如果自动发布未触发，可在 Actions 中手动运行 `Release Publish`。

## 常见问题

- PyPI README 图片不显示：
	- 使用 GitHub Raw 绝对链接，不要用仓库相对路径
- 聚合平台连接失败：
	- 检查 `OPENAI_BASE_URL` 是否为 OpenAI 兼容地址且通常带 `/v1`
	- 确认 `LLM_PROVIDER=openai` 与 `OPENAI_API_KEY` 匹配

## 许可证

本项目使用 MIT License，详见 `LICENSE` 文件。