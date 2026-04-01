"""Bash command execution tool."""

import asyncio
import time
from pathlib import Path

from mini_claude.core import ToolResult, ToolDefinition
from .base import Tool


class BashTool(Tool):
    """Execute bash commands."""

    name = "bash"
    description = "Execute a bash command and return the output"

    def __init__(self, work_dir: str = "."):
        """Initialize bash tool.

        Args:
            work_dir: Working directory for commands
        """
        self.work_dir = Path(work_dir).resolve()

    @property
    def definition(self) -> ToolDefinition:
        """Return tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute",
                    }
                },
                "required": ["command"],
            },
        }

    async def execute(self, command: str) -> ToolResult:
        """Execute a bash command.

        Args:
            command: The bash command to run

        Returns:
            ToolResult with stdout/stderr and error flag
        """
        start_time = time.time()

        try:
            # Create subprocess with cwd safety check
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.work_dir),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    content="Command timed out after 30 seconds",
                    is_error=True,
                )

            # Decode output, handling encoding issues
            output = ""
            if stdout:
                output += stdout.decode("utf-8", errors="ignore")
            if stderr:
                output += stderr.decode("utf-8", errors="ignore")

            # Truncate output if too large (>10KB)
            if len(output) > 10240:
                output = output[:10240] + "\n[output truncated]"

            elapsed = time.time() - start_time
            return ToolResult(
                content=f"{output}\n[took {elapsed:.2f}s]" if output else f"[took {elapsed:.2f}s]",
                is_error=process.returncode != 0,
            )

        except Exception as e:
            return ToolResult(
                content=f"Failed to execute command: {e}",
                is_error=True,
            )
