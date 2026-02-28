"""
Memory Tools - Persistent key-value storage for agent memory.
"""

import os
import json

from tools.base import BaseTool, ToolArg, ToolResult


MEMORY_FILE = ".agent_memory.json"


def _get_memory_path(working_directory: str) -> str:
    return os.path.join(os.path.abspath(working_directory), MEMORY_FILE)


def _load_memory(working_directory: str) -> dict:
    path = _get_memory_path(working_directory)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_memory_file(working_directory: str, memory: dict) -> None:
    path = _get_memory_path(working_directory)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


class SaveMemoryTool(BaseTool):
    """Save a key-value pair to persistent memory."""

    TOOL_NAME = "save_memory"
    TOOL_DESCRIPTION = "Store a key-value pair in persistent memory. Use for remembering project context, preferences, or important info."
    TOOL_ARGS = [
        ToolArg(
            name="key",
            type="string",
            description="The key to store the value under",
            required=True,
        ),
        ToolArg(
            name="value",
            type="string",
            description="The value to store",
            required=True,
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, working_directory: str = ".", key: str = "", value: str = "", **kwargs) -> ToolResult:
        try:
            memory = _load_memory(working_directory)
            memory[key] = value
            _save_memory_file(working_directory, memory)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "key": key,
                "saved": True,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class GetMemoryTool(BaseTool):
    """Retrieve a value from memory."""

    TOOL_NAME = "get_memory"
    TOOL_DESCRIPTION = "Retrieve a value from persistent memory by key, or list all keys if no key provided."
    TOOL_ARGS = [
        ToolArg(
            name="key",
            type="string",
            description="The key to retrieve. If not provided, lists all keys.",
            required=False,
        ),
    ]

    def run(self, working_directory: str = ".", key: str = None, **kwargs) -> ToolResult:
        try:
            memory = _load_memory(working_directory)
            
            if key:
                if key in memory:
                    return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                        "key": key,
                        "value": memory[key],
                    })
                else:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Key not found: {key}")
            else:
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "keys": list(memory.keys()),
                    "count": len(memory),
                })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class DeleteMemoryTool(BaseTool):
    """Delete a key from memory."""

    TOOL_NAME = "delete_memory"
    TOOL_DESCRIPTION = "Delete a key from persistent memory."
    TOOL_ARGS = [
        ToolArg(
            name="key",
            type="string",
            description="The key to delete",
            required=True,
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, working_directory: str = ".", key: str = "", **kwargs) -> ToolResult:
        try:
            memory = _load_memory(working_directory)
            
            if key not in memory:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Key not found: {key}")
            
            del memory[key]
            _save_memory_file(working_directory, memory)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "key": key,
                "deleted": True,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))
