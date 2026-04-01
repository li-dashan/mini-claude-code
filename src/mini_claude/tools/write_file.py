"""File writing tool."""

from pathlib import Path

from mini_claude.core import ToolResult, ToolDefinition
from .base import Tool


class WriteFileTool(Tool):
    """Write contents to a file."""

    name = "write_file"
    description = "Write contents to a file (creates file if it doesn't exist)"

    def __init__(self, work_dir: str = "."):
        """Initialize write file tool.

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
                        "description": "Path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        }

    async def execute(self, path: str, content: str) -> ToolResult:
        """Write to a file.

        Args:
            path: File path relative to work_dir
            content: Content to write

        Returns:
            ToolResult with success message
        """
        try:
            file_path = (self.work_dir / path).resolve()

            # Security check: ensure file is within work_dir
            if not str(file_path).startswith(str(self.work_dir)):
                return ToolResult(
                    content=f"Access denied: path is outside work directory",
                    is_error=True,
                )

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                content=f"Successfully wrote {len(content)} chars to {path}",
                is_error=False,
            )

        except Exception as e:
            return ToolResult(
                content=f"Failed to write file: {e}",
                is_error=True,
            )
