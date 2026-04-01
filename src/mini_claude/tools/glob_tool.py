"""File globbing tool."""

import glob
from pathlib import Path

from mini_claude.core import ToolResult, ToolDefinition
from .base import Tool


class GlobTool(Tool):
    """Search for files matching a glob pattern."""

    name = "glob"
    description = "Search for files matching a glob pattern"

    def __init__(self, work_dir: str = "."):
        """Initialize glob tool.

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
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to search for",
                    }
                },
                "required": ["pattern"],
            },
        }

    async def execute(self, pattern: str) -> ToolResult:
        """Execute a glob pattern search.

        Args:
            pattern: Glob pattern (e.g., "**/*.py")

        Returns:
            ToolResult with matching file paths
        """
        try:
            # Use glob to find matching files
            matches = glob.glob(
                str(self.work_dir / pattern),
                recursive=True,
            )

            # Convert to relative paths and filter out ignored directories
            ignored_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
            filtered_matches = []

            for match in matches:
                # Skip if it's a pyc file
                if match.endswith(".pyc"):
                    continue

                # Skip if path contains ignored directories
                path_parts = Path(match).parts
                if any(part in ignored_dirs for part in path_parts):
                    continue

                relative = Path(match).relative_to(self.work_dir)
                filtered_matches.append(str(relative))

            # Sort and limit results
            filtered_matches.sort()
            if len(filtered_matches) > 200:
                result = "\n".join(filtered_matches[:200])
                result += f"\n[showing 200 of {len(filtered_matches)} matches]"
            else:
                result = "\n".join(filtered_matches) if filtered_matches else "(no matches)"

            return ToolResult(
                content=result,
                is_error=False,
            )

        except Exception as e:
            return ToolResult(
                content=f"Glob search failed: {e}",
                is_error=True,
            )
