<p align="center">
	<img src="https://raw.githubusercontent.com/li-dashan/mini-claude-code/main/assets/logo.svg" width="136" alt="mini-claude-code logo" />
</p>

<h1 align="center">mini-claude-code</h1>

<p align="center">
	A Python project for learning AI Agent architecture.<br/>
	The goal is to replicate the core workflow of a "terminal assistant with tool calling" using a minimal, readable implementation.
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

> 中文文档请见 [README.zh-CN.md](README.zh-CN.md)

## Preview

<p align="center">
	<img src="https://raw.githubusercontent.com/li-dashan/mini-claude-code/main/assets/tui-screenshot-placeholder.png" alt="mini-claude TUI screenshot" width="100%" />
</p>

## Highlights

- **Dual Provider**: Supports Anthropic / OpenAI via a unified `LLMProvider` abstraction
- **OpenAI-Compatible Platforms**: Supports `OPENAI_BASE_URL` (e.g. 147api)
- **Agentic Loop**: Streaming output + tool calling + multi-turn iteration
- **Multi-Tool System**: `bash` / `read_file` / `write_file` / `glob`
- **Two Terminal UIs**: `simple` (Rich REPL) and `tui` (Textual interface)
- **Buddy Pet**: Multiple character presets (appearance / traits / backstory / stats), permanently assigned by username+hostname — no switching
- **Thinking Animation + Tool Feedback**: Dynamic expressions while thinking; tool success/failure affects mood and trust level
- **Runtime Config Management**: `/show-config`, `/set-config`, with automatic persistence to `.env`
- **Tool Visualization & Manual Invocation**: `/tools`, `/tool <name> <json-args>`
- **Enhanced TUI Interaction**: Tab command completion, config key completion, ↑↓ input history
- **Readability-Oriented**: Clean code structure, ideal for learning and customization

## Quick Start

### 1. Install

Option 1 (recommended, uv):

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Option 2 (pip):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Configure at least one of the following:

- `ANTHROPIC_API_KEY` (when `LLM_PROVIDER=anthropic`)
- `OPENAI_API_KEY` (when `LLM_PROVIDER=openai`)

Common configuration:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-sonnet-4-5-20251022
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
# OPENAI_BASE_URL=https://api.147ai.cn/v1
MAX_ITERATIONS=10
WORK_DIR=.
UI_MODE=tui
```

Notes:

- Setting `UI_MODE=tui` launches the Textual TUI
- Default `UI_MODE=tui` uses the Textual TUI
- When using aggregator platforms like 147api:
	- `LLM_PROVIDER=openai`
	- `OPENAI_API_KEY=<platform key>`
	- `OPENAI_BASE_URL=<OpenAI-compatible base URL>` (usually includes `/v1`)

### 2.1 Config File Lookup Priority

On startup, `mini-claude` loads environment variables in the following order (stops at first match):

1. File specified by `MINI_CLAUDE_ENV_FILE`
2. `.env` found by walking up from the current working directory
3. `.env` near the package/project root
4. User-level config: `~/.config/mini-claude/.env`, `~/.mini-claude/.env`
5. `.env.example` found by walking up from the current working directory
6. `.env.example` near the package/project root

This means you can run `mini-claude` from any path and point to a specific config file via `MINI_CLAUDE_ENV_FILE`.

### 3. Run

```bash
mini-claude
```

Or:

```bash
python -m mini_claude.main
```

## Interactive Commands

- `/exit` — Quit
- `/clear` — Clear context history
- `/history` — Show estimated token count for current context
- `/buddy` — View buddy's current status and roster
- `/profile` — View buddy's full profile page (with stat visualization)
- `/pet` — Pet your buddy to increase trust
- `/feed` — Feed your buddy to restore energy
- `/show-config [KEY]` — Show all or a specific runtime config value
- `/set-config <KEY> <VALUE>` — Update config and write back to `.env`
- `/tools` — List all registered tools
- `/tool <NAME> <JSON_ARGS>` — Manually invoke a tool (useful for debugging/learning)

Examples:

```bash
/show-config
/set-config MAX_ITERATIONS 20
/tools
/tool bash {"command":"ls -la"}
```

Supported runtime config keys:

- `LLM_PROVIDER`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `MAX_ITERATIONS`
- `WORK_DIR`
- `system_prompt`

## Agentic Loop Core

Key flow of `QueryEngine.run()`:

1. Record user input to context
2. Stream LLM response and output text in real time
3. Collect tool call requests
4. Execute tools concurrently and write results back
5. Loop within `max_iterations` until the model ends the current turn

This structure supports "think → call tool → think again" iteration within a single turn.

## Project Structure

```text
src/mini_claude/
	main.py                  # Entry point; assembles Provider / Tool / UI
	core/
		config.py              # Runtime config management (show/set-config + .env persistence)
		context_manager.py     # Context and message management
		query_engine.py        # Agentic Loop core
		types.py               # Global type definitions
	llm/
		provider.py            # LLM abstract interface
		anthropic_provider.py  # Anthropic implementation
		openai_provider.py     # OpenAI / OpenAI-compatible implementation
	tools/
		base.py                # Tool abstract base class
		registry.py            # Tool registration and dispatch
		bash.py                # Bash execution
		read_file.py           # File reading
		write_file.py          # File writing
		glob_tool.py           # Glob search
	ui/
		buddy.py               # Buddy virtual pet system
		simple_repl.py         # Rich terminal REPL
		tui/
			app.py               # Textual TUI
```

## Development

Install development dependencies:

```bash
pip install -e .[dev]
```

Type checking:

```bash
mypy src
```

Tests:

```bash
pytest
```

## Release Process (GitHub + PyPI)

The project is configured with:

- **Release Please**: Automatically generates release PRs / tags / GitHub Releases
- **Auto PyPI publish**: Builds and uploads after a release is created
- **Manual fallback publish**: `Release Publish` workflow (`workflow_dispatch`)

Recommended release steps:

1. Commit using Conventional Commits (`feat:` / `fix:` etc.)
2. Merge the release PR generated by release-please
3. Wait for GitHub Actions to complete the publish
4. Confirm the new version is visible on PyPI

If the auto-publish doesn't trigger, manually run `Release Publish` in Actions.

## FAQ

- **PyPI README images not showing**:
	- Use absolute GitHub Raw links; do not use repository-relative paths
- **Aggregator platform connection failure**:
	- Check that `OPENAI_BASE_URL` is an OpenAI-compatible address, usually including `/v1`
	- Confirm `LLM_PROVIDER=openai` matches `OPENAI_API_KEY`

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.