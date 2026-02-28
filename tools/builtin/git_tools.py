"""
Git Operations Tools - Version control management.
"""

import os
import subprocess

from tools.base import BaseTool, ToolArg, ToolResult


class GitStatusTool(BaseTool):
    """Show git repository status."""

    TOOL_NAME = "git_status"
    TOOL_DESCRIPTION = "Show the current git status including staged, unstaged, and untracked files."
    TOOL_ARGS = []

    def run(self, working_directory: str = ".", **kwargs) -> ToolResult:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=os.path.abspath(working_directory),
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.stderr or "Not a git repository")
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={"status": result.stdout})
            
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error="Git command timed out")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class GitDiffTool(BaseTool):
    """Show git diff."""

    TOOL_NAME = "git_diff"
    TOOL_DESCRIPTION = "Show file changes. Use staged=true for staged changes, or specify a file path."
    TOOL_ARGS = [
        ToolArg(
            name="staged",
            type="boolean",
            description="Show staged changes only (default: False)",
            required=False,
            default=False,
        ),
        ToolArg(
            name="path",
            type="string",
            description="Specific file to diff",
            required=False,
        ),
    ]

    def run(self, working_directory: str = ".", staged: bool = False, path: str = None, **kwargs) -> ToolResult:
        try:
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--cached")
            if path:
                cmd.append("--")
                cmd.append(path)
            
            result = subprocess.run(
                cmd,
                cwd=os.path.abspath(working_directory),
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.stderr)
            
            diff = result.stdout
            if len(diff) > 10000:
                diff = diff[:10000] + "\n... [truncated]"
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={"diff": diff})
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class GitLogTool(BaseTool):
    """Show git commit history."""

    TOOL_NAME = "git_log"
    TOOL_DESCRIPTION = "Show recent commit history with messages and authors."
    TOOL_ARGS = [
        ToolArg(
            name="count",
            type="integer",
            description="Number of commits to show (default: 10)",
            required=False,
            default=10,
        ),
    ]

    def run(self, working_directory: str = ".", count: int = 10, **kwargs) -> ToolResult:
        try:
            result = subprocess.run(
                ["git", "log", f"-{min(count, 50)}", "--oneline", "--decorate"],
                cwd=os.path.abspath(working_directory),
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.stderr)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={"log": result.stdout})
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class GitCommitTool(BaseTool):
    """Create a git commit."""

    TOOL_NAME = "git_commit"
    TOOL_DESCRIPTION = "Stage all changes and create a commit with the given message."
    TOOL_ARGS = [
        ToolArg(
            name="message",
            type="string",
            description="Commit message",
            required=True,
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, working_directory: str = ".", message: str = "", **kwargs) -> ToolResult:
        try:
            cwd = os.path.abspath(working_directory)
            
            # Stage all changes
            stage_result = subprocess.run(
                ["git", "add", "-A"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if stage_result.returncode != 0:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Failed to stage: {stage_result.stderr}")
            
            # Create commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if commit_result.returncode != 0:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=commit_result.stderr)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "message": message,
                "output": commit_result.stdout,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class GitBranchTool(BaseTool):
    """Manage git branches."""

    TOOL_NAME = "git_branch"
    TOOL_DESCRIPTION = "List, create, switch, or delete git branches."
    TOOL_ARGS = [
        ToolArg(
            name="action",
            type="string",
            description="Action to perform: list, create, switch, delete",
            required=True,
            enum=["list", "create", "switch", "delete"],
        ),
        ToolArg(
            name="name",
            type="string",
            description="Branch name (required for create, switch, delete)",
            required=False,
        ),
    ]
    IS_DESTRUCTIVE = True  # create/switch/delete modify state

    def run(self, working_directory: str = ".", action: str = "list", name: str = None, **kwargs) -> ToolResult:
        try:
            cwd = os.path.abspath(working_directory)
            
            if action == "list":
                result = subprocess.run(
                    ["git", "branch", "-a"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={"branches": result.stdout})
            
            if not name:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Branch name required for {action}")
            
            if action == "create":
                cmd = ["git", "checkout", "-b", name]
            elif action == "switch":
                cmd = ["git", "checkout", name]
            elif action == "delete":
                cmd = ["git", "branch", "-d", name]
            else:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Unknown action: {action}")
            
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.stderr)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "action": action,
                "branch": name,
                "output": result.stdout or result.stderr,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))
