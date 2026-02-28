"""
Shell & System Tools - Execute commands safely.
"""

import os
import subprocess
import shlex

from tools.base import BaseTool, ToolArg, ToolResult


# Allowed commands (whitelist for safety)
ALLOWED_COMMANDS = {
    # File operations
    "ls", "cat", "head", "tail", "wc", "find", "grep", "awk", "sed",
    "cp", "mv", "mkdir", "rmdir", "touch", "chmod",
    # Development
    "python", "python3", "pip", "pip3", "node", "npm", "npx",
    "cargo", "rustc", "go", "java", "javac",
    # Build tools
    "make", "cmake", "gradle", "mvn",
    # Utilities
    "echo", "printf", "date", "which", "whereis", "env",
    "curl", "wget", "tar", "unzip", "zip", "gzip",
    # Process
    "ps", "top", "kill",
    # Disk
    "df", "du",
}

# Blocked commands (blacklist for safety)
BLOCKED_COMMANDS = {
    "rm", "sudo", "su", "chmod 777", "dd", "mkfs", "fdisk",
    "shutdown", "reboot", "init", "systemctl",
}

# Dangerous patterns that should be blocked
BLOCKED_PATTERNS = [
    r'rm\s+-rf',  # Recursive force delete
    r'>\s*/dev/',  # Writing to devices
    r'\|\s*(ba)?sh',  # Pipe to shell
    r'\|\s*bash',  # Pipe to bash
    r'curl.*\|',  # curl pipe
    r'wget.*\|',  # wget pipe  
    r';\s*(ba)?sh',  # Command chain to shell
    r'`.*`',  # Backtick command substitution
    r'\$\(.*\)',  # Command substitution
    r'nc\s+-[el]',  # Netcat listeners/exec
    r'ncat.*-e',  # Ncat exec
    r'python\s+-c',  # Python inline
    r'python3\s+-c',  # Python3 inline
    r'perl\s+-e',  # Perl inline
    r'ruby\s+-e',  # Ruby inline
    r'base64.*\|',  # Base64 decode pipe
    r'eval\s+',  # Eval commands
    r'exec\s+',  # Exec commands
    r'nohup\s+',  # Background persistent
    r'screen\s+-dm',  # Screen detached
    r'tmux\s+new',  # Tmux session
    r'/etc/passwd',  # Sensitive files
    r'/etc/shadow',
    r'\.ssh/',  # SSH directory
    r'\.gnupg/',  # GPG directory
    r'\.aws/',  # AWS credentials
    r'id_rsa',  # SSH keys
    r'\.bash_history',  # Command history
]


class ShellCommandTool(BaseTool):
    """Execute shell commands safely."""

    TOOL_NAME = "shell_command"
    TOOL_DESCRIPTION = "Execute a shell command in the working directory. Dangerous commands are blocked. Use for build/run tasks."
    TOOL_ARGS = [
        ToolArg(
            name="command",
            type="string",
            description="The shell command to execute",
            required=True,
        ),
        ToolArg(
            name="timeout",
            type="integer",
            description="Timeout in seconds (default: 60, max: 300)",
            required=False,
            default=60,
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, working_directory: str = ".", command: str = "", timeout: int = 60, **kwargs) -> ToolResult:
        import re
        
        try:
            timeout = min(timeout, 300)  # Cap timeout
            
            # Optional local approval gate for shell commands
            if os.getenv("JARVIS_REQUIRE_LOCAL_SHELL_APPROVAL", "false").lower() == "true":
                approval_file = os.getenv("JARVIS_SHELL_APPROVAL_FILE", ".jarvis_shell_approve")
                approval_path = os.path.join(os.path.abspath(working_directory), approval_file)
                token = os.getenv("JARVIS_SHELL_APPROVAL_TOKEN", "").strip()
                try:
                    with open(approval_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                except FileNotFoundError:
                    return ToolResult(
                        ok=False,
                        tool=self.TOOL_NAME,
                        error=f"Local approval required. Create {approval_file} in working directory."
                    )
                if token and content != token:
                    return ToolResult(
                        ok=False,
                        tool=self.TOOL_NAME,
                        error="Local approval token missing or invalid."
                    )
                if os.getenv("JARVIS_SHELL_APPROVAL_ONCE", "false").lower() == "true":
                    try:
                        os.remove(approval_path)
                    except OSError:
                        pass
            
            # Parse command
            try:
                parts = shlex.split(command)
                base_cmd = parts[0] if parts else ""
            except ValueError:
                base_cmd = command.split()[0] if command.split() else ""
            
            # Enforce allowlist for base command
            if base_cmd and base_cmd not in ALLOWED_COMMANDS:
                return ToolResult(
                    ok=False,
                    tool=self.TOOL_NAME,
                    error=f"Command '{base_cmd}' is not in the allowed list"
                )
            
            # Check for blocked commands
            for blocked in BLOCKED_COMMANDS:
                if blocked in command.lower():
                    return ToolResult(
                        ok=False, 
                        tool=self.TOOL_NAME, 
                        error=f"Command '{blocked}' is blocked for safety"
                    )
            
            # Check for dangerous patterns (regex)
            for pattern in BLOCKED_PATTERNS:
                if re.search(pattern, command, re.IGNORECASE):
                    return ToolResult(
                        ok=False,
                        tool=self.TOOL_NAME,
                        error=f"Dangerous pattern detected in command"
                    )
            
            # Validate working directory
            working_dir_abs = os.path.abspath(working_directory)
            if not os.path.isdir(working_dir_abs):
                return ToolResult(
                    ok=False, 
                    tool=self.TOOL_NAME, 
                    error=f"Working directory does not exist: {working_directory}"
                )
            
            # Security: Ensure command doesn't escape working directory
            # Block absolute paths outside working dir
            if re.search(r'(?<![.\w])/(?!tmp\b|app\b)', command):
                # Check if it's trying to access outside paths
                abs_paths = re.findall(r'(?<![.\w])(/[^\s;|&]+)', command)
                for path in abs_paths:
                    if not path.startswith(working_dir_abs) and path not in ['/dev/null', '/tmp']:
                        return ToolResult(
                            ok=False,
                            tool=self.TOOL_NAME,
                            error=f"Access to path outside working directory blocked: {path}"
                        )
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir_abs,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            
            # Truncate long output
            if len(output) > 10000:
                output = output[:10000] + "\n... [truncated]"
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "command": command,
                "exit_code": result.returncode,
                "output": output,
            })
            
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class RunPythonFileTool(BaseTool):
    """Execute a Python file."""

    TOOL_NAME = "run_python_file"
    TOOL_DESCRIPTION = "Execute a Python file with optional arguments. Returns stdout/stderr."
    TOOL_ARGS = [
        ToolArg(
            name="path",
            type="string",
            description="Relative path to the Python file",
            required=True,
        ),
        ToolArg(
            name="args",
            type="string",
            description="Command line arguments to pass to the script",
            required=False,
        ),
        ToolArg(
            name="timeout",
            type="integer",
            description="Timeout in seconds (default: 60)",
            required=False,
            default=60,
        ),
    ]

    def run(self, working_directory: str = ".", path: str = "", args: str = "", timeout: int = 60, **kwargs) -> ToolResult:
        try:
            target = os.path.join(os.path.abspath(working_directory), path)
            
            # Security check
            if not os.path.abspath(target).startswith(os.path.abspath(working_directory)):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error="Path outside working directory")
            
            if not os.path.exists(target):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"File not found: {path}")
            
            if not target.endswith(".py"):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error="File must be a .py file")
            
            # Build command
            cmd = ["python", target]
            if args:
                cmd.extend(shlex.split(args))
            
            result = subprocess.run(
                cmd,
                cwd=os.path.abspath(working_directory),
                capture_output=True,
                text=True,
                timeout=min(timeout, 300),
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            
            if len(output) > 10000:
                output = output[:10000] + "\n... [truncated]"
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "path": path,
                "exit_code": result.returncode,
                "output": output,
            })
            
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Script timed out after {timeout}s")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))
