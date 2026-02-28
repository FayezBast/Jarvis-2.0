"""
Tool Registry - Auto-discovery and management of tools.

The registry:
- Auto-discovers tools from the tools/ directory
- Validates tool implementations
- Provides the dispatcher with tool lookups
- Generates function declarations for the AI model
"""

import importlib
import pkgutil
import logging
from typing import Dict, List, Optional, Any

from google.genai import types

from tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._loaded = False

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Tool must inherit from BaseTool, got {type(tool)}")
        
        name = tool.TOOL_NAME
        if name in self._tools:
            logger.warning(f"Tool '{name}' is already registered, overwriting")
        
        self._tools[name] = tool
        logger.debug(f"Registered tool: {name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all(self) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return self._tools.copy()
    
    def filter_tools(self, allowed: List[str]) -> int:
        """Restrict registry to an allowlist of tool names."""
        allowed_set = set(allowed)
        original = len(self._tools)
        self._tools = {name: tool for name, tool in self._tools.items() if name in allowed_set}
        return original - len(self._tools)

    def auto_discover(self, package_name: str = "tools.builtin") -> int:
        """
        Auto-discover and register tools from a package.
        
        Tools are discovered by looking for classes that inherit from BaseTool.
        
        Returns the number of tools discovered.
        """
        if self._loaded:
            return len(self._tools)

        count = 0
        try:
            package = importlib.import_module(package_name)
            
            for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
                try:
                    module = importlib.import_module(f"{package_name}.{modname}")
                    
                    # Look for tool classes in the module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        
                        # Check if it's a tool class (not BaseTool itself)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseTool) and 
                            attr is not BaseTool):
                            try:
                                tool_instance = attr()
                                self.register(tool_instance)
                                count += 1
                            except Exception as e:
                                logger.error(f"Failed to instantiate tool {attr_name}: {e}")
                                
                except Exception as e:
                    logger.error(f"Failed to load module {modname}: {e}")
                    
        except ImportError as e:
            logger.warning(f"Could not import package {package_name}: {e}")

        self._loaded = True
        logger.info(f"Auto-discovered {count} tools from {package_name}")
        return count

    def get_function_declarations(self) -> types.Tool:
        """
        Generate Gemini function declarations for all registered tools.
        
        Returns a types.Tool object that can be passed to the model.
        """
        declarations = []
        
        for tool in self._tools.values():
            # Convert our schema to Gemini schema
            schema = tool.get_schema()
            
            properties = {}
            for name, prop in schema["parameters"]["properties"].items():
                prop_schema = types.Schema(
                    type=self._map_type(prop.get("type", "string")),
                    description=prop.get("description", ""),
                )
                if "enum" in prop:
                    prop_schema.enum = prop["enum"]
                properties[name] = prop_schema
            
            declaration = types.FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=properties,
                    required=schema["parameters"].get("required", []),
                ),
            )
            declarations.append(declaration)
        
        return types.Tool(function_declarations=declarations)

    def _map_type(self, type_str: str) -> types.Type:
        """Map string type to Gemini Type."""
        type_mapping = {
            "string": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "array": types.Type.ARRAY,
            "object": types.Type.OBJECT,
        }
        return type_mapping.get(type_str, types.Type.STRING)


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry, initializing if needed."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def init_tools() -> ToolRegistry:
    """Initialize the tool system and auto-discover tools."""
    registry = get_registry()
    registry.auto_discover("tools.builtin")
    return registry
