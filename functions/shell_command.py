import os
import subprocess
import shlex

from google.genai import types

# Commands that are allowed (whitelist approach for safety)
ALLOWED_COMMANDS = {
    # File operations
    "ls", "cat", "head", "tail", "wc", "find", "grep", "awk", "sed",
    "cp", "mv", "mkdir", "rmdir", "touch", "chmod",
    # Development
    "python", "python3", "pip", "pip3", "node", "npm", "npx",
    "cargo", "rustc", "go", "java", "javac",
    # Build tools
    "make", "cmake", "gradle", "mvn",
    # Package managers
    "brew", "apt", "apt-get", "yum",
    # Utilities
    "echo", "printf", "date", "which", "whereis", "env", "export",
    "curl", "wget", "tar", "unzip", "zip", "gzip",
    # Process
    "ps", "top", "kill",
    # Disk
    "df", "du",
    # Network
    "ping", "netstat", "ifconfig", "ip",
}

# Commands that are explicitly blocked
BLOCKED_COMMANDS = {
    "rm", "sudo", "su", "chmod 777", "dd", "mkfs", "fdisk",
    "shutdown", "reboot", "init", "systemctl",
}

schema_shell_command = types.FunctionDeclaration(
    name="shell_command",
    description="Executes a shell command in the working directory. Some dangerous commands are blocked for safety. Use for build commands, running scripts, or system utilities.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "command": types.Schema(
                type=types.Type.STRING,
                description="The shell command to execute",
            ),
            "timeout": types.Schema(
                type=types.Type.INTEGER,
                description="Timeout in seconds (default: 60, max: 300)",
            ),
        },
        required=["command"],
    ),
)


def shell_command(working_directory, command, timeout=60):
    try:
        # Limit timeout
        timeout = min(timeout, 300)

        # Parse command to check the base command
        try:
            parts = shlex.split(command)
            base_cmd = parts[0] if parts else ""
        except ValueError:
            base_cmd = command.split()[0] if command.split() else ""

        # Check for blocked commands
        for blocked in BLOCKED_COMMANDS:
            if blocked in command.lower():
                return f"Error: Command '{blocked}' is blocked for safety. Use the appropriate tool instead (e.g., delete_file for rm)."

        # Validate working directory
        working_dir_abs = os.path.abspath(working_directory)
        if not os.path.isdir(working_dir_abs):
            return f"Error: Working directory does not exist: {working_directory}"

        # Execute the command
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir_abs,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        output += f"Exit code: {result.returncode}"

        # Truncate if too long
        if len(output) > 10000:
            output = output[:10000] + "\n\n[...Output truncated at 10000 characters]"

        return output

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: {e}"
