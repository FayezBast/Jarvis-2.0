"""
Code Execution Tools - Run code snippets in various languages.
"""

import os
import subprocess
import tempfile
import shutil
from typing import Optional

from tools.base import BaseTool, ToolArg, ToolResult


class PythonExecTool(BaseTool):
    """Execute Python code snippets."""

    TOOL_NAME = "python_exec"
    TOOL_DESCRIPTION = "Execute Python code and return the output. Great for calculations, data processing, or testing snippets."
    TOOL_ARGS = [
        ToolArg(
            name="code",
            type="string",
            description="Python code to execute",
            required=True,
        ),
        ToolArg(
            name="timeout",
            type="integer",
            description="Execution timeout in seconds (default: 30)",
            required=False,
            default=30,
        ),
    ]

    def run(self, code: str = "", timeout: int = 30, working_directory: str = ".", **kwargs) -> ToolResult:
        try:
            timeout = min(timeout, 60)  # Cap at 60 seconds
            
            # Create temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                result = subprocess.run(
                    ["python", temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=os.path.abspath(working_directory),
                )
                
                output = result.stdout
                if result.stderr:
                    output += f"\n[stderr]\n{result.stderr}"
                
                # Truncate long output
                if len(output) > 10000:
                    output = output[:10000] + "\n... [truncated]"
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "exit_code": result.returncode,
                    "output": output,
                    "success": result.returncode == 0,
                })
                
            finally:
                os.unlink(temp_file)
                
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Execution timed out after {timeout}s")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class NodeExecTool(BaseTool):
    """Execute JavaScript/Node.js code snippets."""

    TOOL_NAME = "node_exec"
    TOOL_DESCRIPTION = "Execute JavaScript code using Node.js. Great for JS calculations, JSON processing, etc."
    TOOL_ARGS = [
        ToolArg(
            name="code",
            type="string",
            description="JavaScript code to execute",
            required=True,
        ),
        ToolArg(
            name="timeout",
            type="integer",
            description="Execution timeout in seconds (default: 30)",
            required=False,
            default=30,
        ),
    ]

    def run(self, code: str = "", timeout: int = 30, working_directory: str = ".", **kwargs) -> ToolResult:
        # Check if node is available
        if not shutil.which("node"):
            return ToolResult(ok=False, tool=self.TOOL_NAME, error="Node.js not found. Install Node.js to use this tool.")
        
        try:
            timeout = min(timeout, 60)
            
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                result = subprocess.run(
                    ["node", temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=os.path.abspath(working_directory),
                )
                
                output = result.stdout
                if result.stderr:
                    output += f"\n[stderr]\n{result.stderr}"
                
                if len(output) > 10000:
                    output = output[:10000] + "\n... [truncated]"
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "exit_code": result.returncode,
                    "output": output,
                    "success": result.returncode == 0,
                })
                
            finally:
                os.unlink(temp_file)
                
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Execution timed out after {timeout}s")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class BashExecTool(BaseTool):
    """Execute bash scripts."""

    TOOL_NAME = "bash_exec"
    TOOL_DESCRIPTION = "Execute a bash script. For complex shell operations with multiple commands."
    TOOL_ARGS = [
        ToolArg(
            name="script",
            type="string",
            description="Bash script to execute",
            required=True,
        ),
        ToolArg(
            name="timeout",
            type="integer",
            description="Execution timeout in seconds (default: 30)",
            required=False,
            default=30,
        ),
    ]
    IS_DESTRUCTIVE = True

    # Blocked patterns for safety
    BLOCKED_PATTERNS = [
        "rm -rf /",
        "rm -rf ~",
        "sudo rm",
        "> /dev/sda",
        "mkfs",
        "dd if=",
        ":(){:|:&};:",  # Fork bomb
        "chmod -R 777 /",
    ]

    def run(self, script: str = "", timeout: int = 30, working_directory: str = ".", **kwargs) -> ToolResult:
        # Safety check
        script_lower = script.lower()
        for blocked in self.BLOCKED_PATTERNS:
            if blocked.lower() in script_lower:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Blocked dangerous pattern: {blocked}")
        
        try:
            timeout = min(timeout, 60)
            
            result = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.path.abspath(working_directory),
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            
            if len(output) > 10000:
                output = output[:10000] + "\n... [truncated]"
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "exit_code": result.returncode,
                "output": output,
                "success": result.returncode == 0,
            })
            
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Script timed out after {timeout}s")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class CalculatorTool(BaseTool):
    """Safe mathematical expression evaluator."""

    TOOL_NAME = "calculate"
    TOOL_DESCRIPTION = "Evaluate mathematical expressions safely. Supports basic math, trig, logarithms, etc."
    TOOL_ARGS = [
        ToolArg(
            name="expression",
            type="string",
            description="Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)', 'sin(pi/2)')",
            required=True,
        ),
    ]

    # Safe math functions
    SAFE_FUNCTIONS = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "pow": pow,
        "int": int,
        "float": float,
    }

    def run(self, expression: str = "", **kwargs) -> ToolResult:
        import math
        
        # Add math functions
        safe_dict = {
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
            "inf": math.inf,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            "atan2": math.atan2,
            "log": math.log,
            "log10": math.log10,
            "log2": math.log2,
            "exp": math.exp,
            "ceil": math.ceil,
            "floor": math.floor,
            "factorial": math.factorial,
            "gcd": math.gcd,
            "degrees": math.degrees,
            "radians": math.radians,
            **self.SAFE_FUNCTIONS,
        }
        
        # Block dangerous patterns
        dangerous = ["import", "exec", "eval", "open", "file", "__", "os.", "sys.", "subprocess"]
        for d in dangerous:
            if d in expression:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Expression contains blocked pattern: {d}")
        
        try:
            # Evaluate safely
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "expression": expression,
                "result": result,
                "type": type(result).__name__,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Evaluation error: {e}")
