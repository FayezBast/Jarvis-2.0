"""
System Tools - System information, clipboard, app launching, and more.
"""

import os
import subprocess
import platform
import shutil
from datetime import datetime

from tools.base import BaseTool, ToolArg, ToolResult


class SystemInfoTool(BaseTool):
    """Get system information."""

    TOOL_NAME = "system_info"
    TOOL_DESCRIPTION = "Get information about the current system: OS, CPU, memory, disk space, Python version, etc."
    TOOL_ARGS = []

    def run(self, **kwargs) -> ToolResult:
        try:
            # Basic info
            info = {
                "os": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "hostname": platform.node(),
                "username": os.getenv("USER") or os.getenv("USERNAME", "unknown"),
                "home_dir": os.path.expanduser("~"),
                "current_dir": os.getcwd(),
                "current_time": datetime.now().isoformat(),
            }
            
            # Disk space
            try:
                total, used, free = shutil.disk_usage("/")
                info["disk"] = {
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "used_percent": round((used / total) * 100, 1),
                }
            except Exception:
                pass
            
            # Environment variables (safe ones)
            info["env"] = {
                "PATH": os.getenv("PATH", "")[:200] + "...",
                "SHELL": os.getenv("SHELL", ""),
                "LANG": os.getenv("LANG", ""),
                "TERM": os.getenv("TERM", ""),
            }
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result=info)
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class ClipboardTool(BaseTool):
    """Read from or write to the system clipboard."""

    TOOL_NAME = "clipboard"
    TOOL_DESCRIPTION = "Read from or write to the system clipboard. Useful for copying code, text, or data."
    TOOL_ARGS = [
        ToolArg(
            name="action",
            type="string",
            description="Action: 'read' to get clipboard content, 'write' to set clipboard content",
            required=True,
            enum=["read", "write"],
        ),
        ToolArg(
            name="content",
            type="string",
            description="Content to write to clipboard (required for 'write' action)",
            required=False,
        ),
    ]

    def run(self, action: str = "read", content: str = None, **kwargs) -> ToolResult:
        system = platform.system()
        
        try:
            if action == "read":
                # Read from clipboard
                if system == "Darwin":  # macOS
                    result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
                    clipboard_content = result.stdout
                elif system == "Linux":
                    result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], 
                                          capture_output=True, text=True, timeout=5)
                    clipboard_content = result.stdout
                elif system == "Windows":
                    result = subprocess.run(["powershell", "-command", "Get-Clipboard"], 
                                          capture_output=True, text=True, timeout=5)
                    clipboard_content = result.stdout
                else:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unsupported OS: {system}")
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "action": "read",
                    "content": clipboard_content,
                    "length": len(clipboard_content),
                })
            
            elif action == "write":
                if not content:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Content required for write action")
                
                if system == "Darwin":  # macOS
                    subprocess.run(["pbcopy"], input=content.encode(), timeout=5)
                elif system == "Linux":
                    subprocess.run(["xclip", "-selection", "clipboard"], input=content.encode(), timeout=5)
                elif system == "Windows":
                    subprocess.run(["clip"], input=content.encode(), timeout=5)
                else:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unsupported OS: {system}")
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "action": "write",
                    "length": len(content),
                    "preview": content[:100] + "..." if len(content) > 100 else content,
                })
            
        except FileNotFoundError:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error="Clipboard utility not found. Install xclip on Linux.")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class AppLauncherTool(BaseTool):
    """Launch applications on the system."""

    TOOL_NAME = "open_app"
    TOOL_DESCRIPTION = "Open an application or file with the default system handler. Can open URLs in browser, files in editors, etc."
    TOOL_ARGS = [
        ToolArg(
            name="target",
            type="string",
            description="What to open: app name (e.g., 'Safari'), file path, or URL",
            required=True,
        ),
        ToolArg(
            name="args",
            type="string",
            description="Optional arguments to pass to the application",
            required=False,
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, target: str = "", args: str = None, **kwargs) -> ToolResult:
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                cmd = ["open"]
                if target.endswith(".app") or not ("." in target or "/" in target):
                    # It's an app
                    cmd.extend(["-a", target])
                else:
                    cmd.append(target)
                if args:
                    cmd.extend(["--args", args])
                    
            elif system == "Linux":
                cmd = ["xdg-open", target]
                
            elif system == "Windows":
                cmd = ["start", "", target]
                
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unsupported OS: {system}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "target": target,
                    "opened": True,
                })
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.stderr or "Failed to open")
                
        except FileNotFoundError:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Cannot open: {target}")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class NotificationTool(BaseTool):
    """Send system notifications."""

    TOOL_NAME = "notify"
    TOOL_DESCRIPTION = "Send a desktop notification to the user. Great for alerting when long tasks complete."
    TOOL_ARGS = [
        ToolArg(
            name="title",
            type="string",
            description="Notification title",
            required=True,
        ),
        ToolArg(
            name="message",
            type="string",
            description="Notification message body",
            required=True,
        ),
        ToolArg(
            name="sound",
            type="boolean",
            description="Play notification sound (default: True)",
            required=False,
            default=True,
        ),
    ]

    def run(self, title: str = "", message: str = "", sound: bool = True, **kwargs) -> ToolResult:
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                sound_part = 'sound name "default"' if sound else ""
                script = f'display notification "{message}" with title "{title}" {sound_part}'
                subprocess.run(["osascript", "-e", script], timeout=5)
                
            elif system == "Linux":
                cmd = ["notify-send", title, message]
                subprocess.run(cmd, timeout=5)
                
            elif system == "Windows":
                # PowerShell toast notification
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $template.SelectSingleNode("//text[@id='1']").InnerText = "{title}"
                $template.SelectSingleNode("//text[@id='2']").InnerText = "{message}"
                '''
                subprocess.run(["powershell", "-command", ps_script], timeout=10)
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unsupported OS: {system}")
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "title": title,
                "message": message,
                "sent": True,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class ScreenshotTool(BaseTool):
    """Take a screenshot."""

    TOOL_NAME = "screenshot"
    TOOL_DESCRIPTION = "Take a screenshot and save it to a file. Useful for documenting or debugging."
    TOOL_ARGS = [
        ToolArg(
            name="output_path",
            type="string",
            description="Path to save the screenshot (default: screenshot.png)",
            required=False,
            default="screenshot.png",
        ),
        ToolArg(
            name="region",
            type="string",
            description="Region to capture: 'full' (entire screen), 'window' (active window), or coordinates 'x,y,w,h'",
            required=False,
            default="full",
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, working_directory: str = ".", output_path: str = "screenshot.png", region: str = "full", **kwargs) -> ToolResult:
        system = platform.system()
        full_path = os.path.join(os.path.abspath(working_directory), output_path)
        
        try:
            if system == "Darwin":  # macOS
                if region == "full":
                    cmd = ["screencapture", "-x", full_path]
                elif region == "window":
                    cmd = ["screencapture", "-x", "-w", full_path]
                else:
                    # Assume coordinates x,y,w,h
                    cmd = ["screencapture", "-x", "-R", region, full_path]
                    
            elif system == "Linux":
                if region == "full":
                    cmd = ["scrot", full_path]
                elif region == "window":
                    cmd = ["scrot", "-u", full_path]
                else:
                    cmd = ["scrot", "-a", region, full_path]
                    
            elif system == "Windows":
                # Use PowerShell to take screenshot
                ps_script = f'''
                Add-Type -AssemblyName System.Windows.Forms
                $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
                $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
                $bitmap.Save("{full_path}")
                '''
                cmd = ["powershell", "-command", ps_script]
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unsupported OS: {system}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if os.path.exists(full_path):
                size = os.path.getsize(full_path)
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "path": output_path,
                    "full_path": full_path,
                    "size_bytes": size,
                })
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.stderr or "Screenshot failed")
                
        except FileNotFoundError:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error="Screenshot utility not found. Install scrot on Linux.")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))
