"""
Date/Time and Utility Tools
"""

import os
import json
import hashlib
import base64
import uuid
from datetime import datetime, timedelta
from typing import Optional

from tools.base import BaseTool, ToolArg, ToolResult


class DateTimeTool(BaseTool):
    """Get current date/time or perform date calculations."""

    TOOL_NAME = "datetime"
    TOOL_DESCRIPTION = "Get current date/time, format dates, or calculate time differences."
    TOOL_ARGS = [
        ToolArg(
            name="action",
            type="string",
            description="Action: 'now' (current time), 'format' (format a date), 'diff' (time difference), 'add' (add to date)",
            required=True,
            enum=["now", "format", "diff", "add"],
        ),
        ToolArg(
            name="date",
            type="string",
            description="Date string for format/diff/add (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
            required=False,
        ),
        ToolArg(
            name="format",
            type="string",
            description="Output format using strftime codes (e.g., '%Y-%m-%d', '%B %d, %Y')",
            required=False,
            default="%Y-%m-%d %H:%M:%S",
        ),
        ToolArg(
            name="days",
            type="integer",
            description="Days to add (for 'add' action, can be negative)",
            required=False,
            default=0,
        ),
        ToolArg(
            name="hours",
            type="integer",
            description="Hours to add (for 'add' action)",
            required=False,
            default=0,
        ),
    ]

    def run(
        self,
        action: str = "now",
        date: str = None,
        format: str = "%Y-%m-%d %H:%M:%S",
        days: int = 0,
        hours: int = 0,
        **kwargs
    ) -> ToolResult:
        try:
            now = datetime.now()
            
            if action == "now":
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "iso": now.isoformat(),
                    "formatted": now.strftime(format),
                    "timestamp": int(now.timestamp()),
                    "timezone": str(now.astimezone().tzinfo),
                    "weekday": now.strftime("%A"),
                })
            
            elif action == "format":
                if not date:
                    dt = now
                else:
                    dt = datetime.fromisoformat(date)
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "input": date or "now",
                    "formatted": dt.strftime(format),
                })
            
            elif action == "diff":
                if not date:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Date required for diff action")
                
                dt = datetime.fromisoformat(date)
                diff = now - dt
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "from": date,
                    "to": now.isoformat(),
                    "days": diff.days,
                    "hours": diff.seconds // 3600,
                    "minutes": (diff.seconds % 3600) // 60,
                    "total_seconds": int(diff.total_seconds()),
                    "human": self._humanize_delta(diff),
                })
            
            elif action == "add":
                base = datetime.fromisoformat(date) if date else now
                result_dt = base + timedelta(days=days, hours=hours)
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "original": base.isoformat(),
                    "added": f"{days} days, {hours} hours",
                    "result": result_dt.isoformat(),
                    "formatted": result_dt.strftime(format),
                })
            
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unknown action: {action}")
                
        except ValueError as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Invalid date format: {e}")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))

    def _humanize_delta(self, delta: timedelta) -> str:
        """Convert timedelta to human-readable string."""
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return f"{abs(total_seconds)} seconds in the future"
        
        if total_seconds < 60:
            return f"{total_seconds} seconds ago"
        elif total_seconds < 3600:
            return f"{total_seconds // 60} minutes ago"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600} hours ago"
        else:
            return f"{delta.days} days ago"


class EncodingTool(BaseTool):
    """Encode and decode data in various formats."""

    TOOL_NAME = "encode"
    TOOL_DESCRIPTION = "Encode or decode data: base64, URL encoding, JSON, hashing (MD5, SHA256)."
    TOOL_ARGS = [
        ToolArg(
            name="action",
            type="string",
            description="Action to perform",
            required=True,
            enum=["base64_encode", "base64_decode", "md5", "sha256", "json_encode", "json_decode", "uuid"],
        ),
        ToolArg(
            name="data",
            type="string",
            description="Data to encode/decode/hash (not required for 'uuid')",
            required=False,
        ),
    ]

    def run(self, action: str = "", data: str = "", **kwargs) -> ToolResult:
        try:
            if action == "base64_encode":
                if not data:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Data required")
                result = base64.b64encode(data.encode()).decode()
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"encoded": result})
            
            elif action == "base64_decode":
                if not data:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Data required")
                result = base64.b64decode(data).decode()
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"decoded": result})
            
            elif action == "md5":
                if not data:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Data required")
                result = hashlib.md5(data.encode()).hexdigest()
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"hash": result, "algorithm": "md5"})
            
            elif action == "sha256":
                if not data:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Data required")
                result = hashlib.sha256(data.encode()).hexdigest()
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"hash": result, "algorithm": "sha256"})
            
            elif action == "json_encode":
                if not data:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Data required")
                # Try to parse as Python literal first
                try:
                    obj = eval(data, {"__builtins__": {}}, {})
                    result = json.dumps(obj, indent=2)
                except Exception:
                    result = json.dumps(data)
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"json": result})
            
            elif action == "json_decode":
                if not data:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Data required")
                result = json.loads(data)
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"decoded": result})
            
            elif action == "uuid":
                result = str(uuid.uuid4())
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"uuid": result})
            
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class WaitTool(BaseTool):
    """Pause execution for a specified duration."""

    TOOL_NAME = "wait"
    TOOL_DESCRIPTION = "Pause execution for a specified number of seconds. Useful for rate limiting or waiting for resources."
    TOOL_ARGS = [
        ToolArg(
            name="seconds",
            type="integer",
            description="Number of seconds to wait (max: 30)",
            required=True,
        ),
        ToolArg(
            name="reason",
            type="string",
            description="Reason for waiting (for logging)",
            required=False,
        ),
    ]

    def run(self, seconds: int = 1, reason: str = None, **kwargs) -> ToolResult:
        import time
        
        # Cap at 30 seconds
        seconds = min(seconds, 30)
        
        time.sleep(seconds)
        
        return ToolResult(ok=True, tool=self.TOOL_NAME, result={
            "waited": seconds,
            "reason": reason or "No reason specified",
        })


class EnvironmentTool(BaseTool):
    """Read environment variables."""

    TOOL_NAME = "get_env"
    TOOL_DESCRIPTION = "Read environment variables. Useful for accessing configuration or secrets."
    TOOL_ARGS = [
        ToolArg(
            name="name",
            type="string",
            description="Environment variable name to read",
            required=True,
        ),
    ]

    # Blocked env vars for security
    BLOCKED_VARS = {"GEMINI_API_KEY", "API_KEY", "SECRET", "PASSWORD", "TOKEN", "PRIVATE_KEY"}

    def run(self, name: str = "", **kwargs) -> ToolResult:
        # Security check
        name_upper = name.upper()
        for blocked in self.BLOCKED_VARS:
            if blocked in name_upper:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Access to {name} is blocked for security")
        
        value = os.getenv(name)
        
        if value is None:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Environment variable not found: {name}")
        
        return ToolResult(ok=True, tool=self.TOOL_NAME, result={
            "name": name,
            "value": value,
        })
