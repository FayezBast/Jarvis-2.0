"""
Tool Dispatcher - Safe execution of tools with validation.

The dispatcher:
- Only allows registered tools
- Validates arguments strictly
- Prevents arbitrary code execution
- Returns structured responses
"""

import logging
from typing import Dict, Any, Optional

from google.genai import types

from tools.registry import get_registry
from tools.base import ToolResult

logger = logging.getLogger(__name__)


class ToolDispatcher:
    """
    Safe dispatcher for tool execution.
    
    Responsibilities:
    - Validate tool exists in registry
    - Validate arguments match schema
    - Execute tool with proper error handling
    - Handle dry-run mode for destructive operations
    - Return structured responses
    """

    def __init__(self, working_directory: str = ".", dry_run: bool = False, verbose: bool = False):
        self.working_directory = working_directory
        self.dry_run = dry_run
        self.verbose = verbose
        self.registry = get_registry()

    def dispatch(self, function_call) -> types.Content:
        """
        Dispatch a function call to the appropriate tool.
        
        Args:
            function_call: The function call from the model
            
        Returns:
            types.Content with the tool response
        """
        function_name = function_call.name or ""
        args = dict(function_call.args) if function_call.args else {}
        
        if self.verbose:
            logger.info(f"Dispatching: {function_name}({args})")
        else:
            print(f" → {function_name}")
        
        # Execute and get result
        result = self._execute(function_name, args)
        
        if self.verbose:
            logger.info(f"Result: {result.to_dict()}")
        
        # Convert to Gemini response format
        return types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_name,
                    response=result.to_dict(),
                )
            ],
        )

    def execute(self, name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the raw ToolResult (no model formatting)."""
        return self._execute(name, args)

    def _execute(self, name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given arguments."""
        
        # Check if tool exists
        tool = self.registry.get(name)
        if tool is None:
            return ToolResult(
                ok=False,
                tool=name,
                error=f"Unknown tool: {name}. Available: {self.registry.list_tools()}"
            )
        
        # Validate arguments
        validation_error = tool.validate_args(args)
        if validation_error:
            return ToolResult(
                ok=False,
                tool=name,
                error=f"Invalid arguments: {validation_error}"
            )
        
        # Handle dry-run for destructive operations
        if self.dry_run and tool.IS_DESTRUCTIVE:
            return ToolResult(
                ok=True,
                tool=name,
                result=f"[DRY-RUN] Would execute {name} with args: {args}"
            )
        
        # Execute the tool
        try:
            # Add working directory to args
            args["working_directory"] = self.working_directory
            result = tool.run(**args)
            return result
        except Exception as e:
            logger.exception(f"Tool {name} failed with exception")
            return ToolResult(
                ok=False,
                tool=name,
                error=f"Execution error: {str(e)}"
            )


def create_dispatcher(
    working_directory: str = ".",
    dry_run: bool = False,
    verbose: bool = False
) -> ToolDispatcher:
    """Create a configured tool dispatcher."""
    return ToolDispatcher(
        working_directory=working_directory,
        dry_run=dry_run,
        verbose=verbose,
    )
