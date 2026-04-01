"""File reading tool."""

from pathlib import Path

from mini_claude.core import ToolResult, ToolDefinition
from .base import Tool


class ReadFileTool(Tool):
    """Read file contents."""

    name = "read_file"
    description = "Read the contents of a file"

    def __init__(self, work_dir: str = "."):
        """Initialize read file tool.

        Args:
            work_dir: Working directory for file operations
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
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read",
                    }
                },
                "required": ["path"],
            },
        }

    async def execute(self, path: str) -> ToolResult:
        """Read a file.

        Args:
            path: File path relative to work_dir

        Returns:
            ToolResult with file contents
        """
        try:
            file_path = (self.work_dir / path).resolve()

            # Security check: ensure file is within work_dir
            if not str(file_path).startswith(str(self.work_dir)):
                return ToolResult(
                    content=f"Access denied: path is outside work directory",
                    is_error=True,
                )

            if not file_path.exists():
                return ToolResult(
                    content=f"File not found: {path}",
                    is_error=True,
                )

            if not file_path.is_file():
                return ToolResult(
                    content=f"Not a file: {path}",
                    is_error=True,
                )

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > 102400:  # 100KB limit
                # Read only first 100KB
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(102400)
                return ToolResult(
                    content=f"{content}\n[file truncated, content is {file_size} bytes]",
                    is_error=False,
                )

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            return ToolResult(
                content=content,
                is_error=False,
            )

        except Exception as e:
            return ToolResult(
                content=f"Failed to read file: {e}",
                is_error=True,
            )
