"""
Base Tool Interface for Jarvis-2.0

Every tool must inherit from BaseTool and implement:
- TOOL_NAME: unique identifier
- TOOL_DESCRIPTION: what the tool does
- TOOL_ARGS: argument schema
- run(**kwargs) -> dict: execution method
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ToolArg:
    """Schema for a single tool argument."""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class ToolResult:
    """Structured response from a tool execution."""
    ok: bool
    tool: str
    result: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-safe dictionary."""
        data = {
            "ok": self.ok,
            "tool": self.tool,
        }
        if self.ok:
            data["result"] = self.result
        else:
            data["error"] = self.error
        return data


class BaseTool(ABC):
    """Abstract base class for all Jarvis tools."""

    @property
    @abstractmethod
    def TOOL_NAME(self) -> str:
        """Unique identifier for the tool."""
        pass

    @property
    @abstractmethod
    def TOOL_DESCRIPTION(self) -> str:
        """Human-readable description of what the tool does."""
        pass

    @property
    @abstractmethod
    def TOOL_ARGS(self) -> List[ToolArg]:
        """List of argument definitions for the tool."""
        pass

    @property
    def IS_DESTRUCTIVE(self) -> bool:
        """Whether this tool modifies state (files, system, etc.)."""
        return False

    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """
        Execute the tool with the given arguments.
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            ToolResult with ok=True/False and result/error
        """
        pass

    def validate_args(self, args: Dict[str, Any]) -> Optional[str]:
        """
        Validate arguments against schema.
        
        Returns None if valid, or error message if invalid.
        """
        for arg in self.TOOL_ARGS:
            if arg.required and arg.name not in args:
                return f"Missing required argument: {arg.name}"
            
            if arg.name in args and args[arg.name] is not None:
                value = args[arg.name]
                
                # Type validation
                type_map = {
                    "string": str,
                    "integer": int,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                expected_type = type_map.get(arg.type)
                if expected_type and not isinstance(value, expected_type):
                    return f"Argument '{arg.name}' must be {arg.type}, got {type(value).__name__}"
                
                # Enum validation
                if arg.enum and value not in arg.enum:
                    return f"Argument '{arg.name}' must be one of: {arg.enum}"
        
        return None

    def get_schema(self) -> Dict[str, Any]:
        """Generate JSON schema for the tool arguments."""
        properties = {}
        required = []
        
        for arg in self.TOOL_ARGS:
            prop = {
                "type": arg.type,
                "description": arg.description,
            }
            if arg.enum:
                prop["enum"] = arg.enum
            if arg.default is not None:
                prop["default"] = arg.default
                
            properties[arg.name] = prop
            
            if arg.required:
                required.append(arg.name)
        
        return {
            "name": self.TOOL_NAME,
            "description": self.TOOL_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }
