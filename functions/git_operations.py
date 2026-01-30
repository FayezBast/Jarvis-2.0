import os
import subprocess

from google.genai import types

schema_git_status = types.FunctionDeclaration(
    name="git_status",
    description="Shows the current git status including staged, unstaged, and untracked files",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={},
    ),
)

schema_git_diff = types.FunctionDeclaration(
    name="git_diff",
    description="Shows git diff for staged or unstaged changes",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "staged": types.Schema(
                type=types.Type.BOOLEAN,
                description="If True, show staged changes (--cached). Default: False (unstaged changes)",
            ),
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="Optional: specific file to diff",
            ),
        },
    ),
)

schema_git_log = types.FunctionDeclaration(
    name="git_log",
    description="Shows recent git commit history",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "count": types.Schema(
                type=types.Type.INTEGER,
                description="Number of commits to show (default: 10)",
            ),
            "oneline": types.Schema(
                type=types.Type.BOOLEAN,
                description="If True, show compact one-line format (default: True)",
            ),
        },
    ),
)

schema_git_commit = types.FunctionDeclaration(
    name="git_commit",
    description="Stages all changes and creates a git commit with the given message",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "message": types.Schema(
                type=types.Type.STRING,
                description="The commit message",
            ),
            "add_all": types.Schema(
                type=types.Type.BOOLEAN,
                description="If True, stage all changes before committing (default: True)",
            ),
        },
        required=["message"],
    ),
)

schema_git_branch = types.FunctionDeclaration(
    name="git_branch",
    description="List, create, or switch git branches",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "action": types.Schema(
                type=types.Type.STRING,
                description="Action: 'list', 'create', 'switch', or 'delete'",
            ),
            "branch_name": types.Schema(
                type=types.Type.STRING,
                description="Branch name (required for create/switch/delete)",
            ),
        },
        required=["action"],
    ),
)


def _run_git_command(working_directory, args, check=True):
    """Helper to run git commands safely."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if check and result.returncode != 0:
            return f"Git error: {result.stderr.strip() or result.stdout.strip()}"
        return result.stdout.strip() or result.stderr.strip() or "Success (no output)"
    except subprocess.TimeoutExpired:
        return "Error: Git command timed out"
    except FileNotFoundError:
        return "Error: Git is not installed or not in PATH"
    except Exception as e:
        return f"Error: {e}"


def git_status(working_directory):
    return _run_git_command(working_directory, ["status"])


def git_diff(working_directory, staged=False, file_path=None):
    args = ["diff"]
    if staged:
        args.append("--cached")
    if file_path:
        args.append("--")
        args.append(file_path)
    
    result = _run_git_command(working_directory, args)
    return result if result else "No changes detected"


def git_log(working_directory, count=10, oneline=True):
    args = ["log", f"-{count}"]
    if oneline:
        args.append("--oneline")
    return _run_git_command(working_directory, args)


def git_commit(working_directory, message, add_all=True):
    if add_all:
        add_result = _run_git_command(working_directory, ["add", "-A"])
        if "error" in add_result.lower():
            return add_result
    
    return _run_git_command(working_directory, ["commit", "-m", message])


def git_branch(working_directory, action, branch_name=None):
    if action == "list":
        return _run_git_command(working_directory, ["branch", "-a"])
    elif action == "create":
        if not branch_name:
            return "Error: branch_name required for create action"
        return _run_git_command(working_directory, ["branch", branch_name])
    elif action == "switch":
        if not branch_name:
            return "Error: branch_name required for switch action"
        return _run_git_command(working_directory, ["checkout", branch_name])
    elif action == "delete":
        if not branch_name:
            return "Error: branch_name required for delete action"
        return _run_git_command(working_directory, ["branch", "-d", branch_name])
    else:
        return f"Error: Unknown action '{action}'. Use: list, create, switch, or delete"
