"""
Go Bridge - Python wrapper for calling Go-based tool binaries.

This module provides Python functions that call high-performance Go binaries
for operations like file search and indexing.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional


# Path to Go binaries
BIN_DIR = Path(__file__).parent.parent / "bin"


def _get_binary_path(name: str) -> Path:
    """Get the path to a Go binary."""
    binary = BIN_DIR / name
    if not binary.exists():
        raise FileNotFoundError(
            f"Go binary '{name}' not found at {binary}. "
            f"Run 'cd tools/go && go build -o ../bin/{name} ./cmd/{name}' to build it."
        )
    return binary


def _run_binary(name: str, args: list[str], timeout: int = 60) -> dict:
    """Run a Go binary and return the JSON output."""
    try:
        binary = _get_binary_path(name)
        result = subprocess.run(
            [str(binary)] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0 and result.stderr:
            return {"success": False, "error": result.stderr}
        
        # Try to parse JSON output
        try:
            return {"success": True, "data": json.loads(result.stdout)}
        except json.JSONDecodeError:
            return {"success": True, "data": result.stdout}
            
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def fast_search(
    pattern: str,
    directory: str = ".",
    regex: bool = False,
    ignore_case: bool = False,
    file_pattern: Optional[str] = None,
    max_results: int = 100,
) -> dict:
    """
    Fast parallel file search using Go binary.
    
    Args:
        pattern: Search pattern (string or regex)
        directory: Directory to search in
        regex: Treat pattern as regex
        ignore_case: Case insensitive search
        file_pattern: File glob pattern (e.g., '*.py')
        max_results: Maximum number of results
        
    Returns:
        dict with 'success', 'data' (matches, count) or 'error'
    """
    args = [
        "-pattern", pattern,
        "-dir", directory,
        "-max", str(max_results),
        "-json",
    ]
    
    if regex:
        args.append("-regex")
    if ignore_case:
        args.append("-i")
    if file_pattern:
        args.extend(["-files", file_pattern])
    
    return _run_binary("fast-search", args)


def index_files(
    directory: str = ".",
    with_hash: bool = False,
    extensions: Optional[str] = None,
    max_depth: int = -1,
    exclude_dirs: Optional[str] = None,
) -> dict:
    """
    Fast parallel file indexing using Go binary.
    
    Args:
        directory: Directory to index
        with_hash: Calculate MD5 hash for each file
        extensions: Filter by extensions (comma-separated, e.g., 'py,go,js')
        max_depth: Maximum directory depth (-1 for unlimited)
        exclude_dirs: Directories to exclude (comma-separated)
        
    Returns:
        dict with 'success', 'data' (files, total_files, total_size, duration) or 'error'
    """
    args = ["-dir", directory]
    
    if with_hash:
        args.append("-hash")
    if extensions:
        args.extend(["-ext", extensions])
    if max_depth >= 0:
        args.extend(["-depth", str(max_depth)])
    if exclude_dirs:
        args.extend(["-exclude", exclude_dirs])
    
    return _run_binary("file-indexer", args)


def analyze_code(
    path: str,
    extensions: Optional[str] = None,
    symbol_type: Optional[str] = None,
    max_depth: int = -1,
) -> dict:
    """
    Analyze code structure using Go binary.
    
    Args:
        path: File or directory to analyze
        extensions: Filter by extensions (comma-separated, e.g., 'py,go,js')
        symbol_type: Filter by symbol type (function, class, method, import)
        max_depth: Maximum directory depth (-1 for unlimited)
        
    Returns:
        dict with 'success', 'data' (files with symbols, imports, etc.) or 'error'
    """
    args = ["-path", path]
    
    if extensions:
        args.extend(["-ext", extensions])
    if symbol_type:
        args.extend(["-type", symbol_type])
    if max_depth >= 0:
        args.extend(["-depth", str(max_depth)])
    
    return _run_binary("code-analyzer", args)


def run_parallel(
    tasks: Optional[list[dict]] = None,
    command: Optional[str] = None,
    files: Optional[list[str]] = None,
    working_dir: str = ".",
    max_workers: int = 0,
    timeout: int = 60,
) -> dict:
    """
    Run multiple tasks in parallel using Go binary.
    
    Args:
        tasks: List of task dicts with 'id', 'command', optional 'dir'
        command: Command template with {file} or {} placeholder
        files: List of files to run command on (used with command)
        working_dir: Working directory for tasks
        max_workers: Max parallel workers (0 = auto)
        timeout: Timeout per task in seconds
        
    Returns:
        dict with 'success', 'data' (results, success_count, fail_count) or 'error'
    """
    args = ["-dir", working_dir, "-workers", str(max_workers), "-timeout", str(timeout)]
    
    if tasks:
        args.extend(["-json", json.dumps(tasks)])
    elif command and files:
        args.extend(["-cmd", command, "-files", ",".join(files)])
    else:
        return {"success": False, "error": "Either 'tasks' or 'command'+'files' must be provided"}
    
    return _run_binary("parallel-runner", args, timeout=timeout * len(files or tasks or [1]) + 10)


def generate_diff(
    old_file: str,
    new_file: str,
    context_lines: int = 3,
) -> dict:
    """
    Generate a unified diff between two files.
    
    Args:
        old_file: Path to the original file
        new_file: Path to the modified file
        context_lines: Lines of context around changes
        
    Returns:
        dict with 'success', 'data' (diff hunks, patch string) or 'error'
    """
    args = ["-mode", "diff", "-old", old_file, "-new", new_file, "-context", str(context_lines)]
    return _run_binary("diff-engine", args)


def apply_diff(
    target_file: str,
    old_text: str,
    new_text: str,
    preview: bool = False,
) -> dict:
    """
    Apply a text replacement to a file.
    
    Args:
        target_file: File to modify
        old_text: Exact text to find and replace
        new_text: Replacement text
        preview: If True, return preview without modifying file
        
    Returns:
        dict with 'success', 'data' or 'error'
    """
    mode = "preview" if preview else "apply"
    args = ["-mode", mode, "-target", target_file, "-old-text", old_text, "-new-text", new_text]
    return _run_binary("diff-engine", args)


def resolve_symbol(
    symbol_name: str,
    directory: str = ".",
    extensions: Optional[str] = None,
    find_defs: bool = True,
    find_refs: bool = True,
    max_depth: int = -1,
) -> dict:
    """
    Find where a symbol is defined and used.
    
    Args:
        symbol_name: Name of the symbol to find
        directory: Directory to search
        extensions: Filter by extensions (comma-separated)
        find_defs: Find definitions
        find_refs: Find references
        max_depth: Max directory depth
        
    Returns:
        dict with 'success', 'data' (definition, references) or 'error'
    """
    args = ["-symbol", symbol_name, "-dir", directory]
    
    if extensions:
        args.extend(["-ext", extensions])
    if not find_defs:
        args.append("-defs=false")
    if not find_refs:
        args.append("-refs=false")
    if max_depth >= 0:
        args.extend(["-depth", str(max_depth)])
    
    return _run_binary("symbol-resolver", args)


def git_analyze(
    mode: str,
    file: Optional[str] = None,
    commit: Optional[str] = None,
    count: int = 10,
    since: Optional[str] = None,
    author: Optional[str] = None,
    repo_path: str = ".",
    lines: Optional[str] = None,
) -> dict:
    """
    Analyze git repository.
    
    Args:
        mode: Operation mode - 'blame', 'log', 'diff', 'status', 'branches', 'changes'
        file: File path (for blame, log)
        commit: Commit hash
        count: Number of commits to show (for log)
        since: Show commits since date (e.g., '1 week ago')
        author: Filter by author
        repo_path: Repository path
        lines: Line range for blame (e.g., '10,20')
        
    Returns:
        dict with 'success', 'data' or 'error'
    """
    args = ["-mode", mode, "-repo", repo_path]
    
    if file:
        args.extend(["-file", file])
    if commit:
        args.extend(["-commit", commit])
    if count != 10:
        args.extend(["-count", str(count)])
    if since:
        args.extend(["-since", since])
    if author:
        args.extend(["-author", author])
    if lines:
        args.extend(["-lines", lines])
    
    return _run_binary("git-analyzer", args)


def watch_files(
    directory: str = ".",
    extensions: Optional[str] = None,
    duration: int = 0,
    exclude_dirs: Optional[str] = None,
    snapshot: bool = False,
    compare_snapshot: Optional[str] = None,
) -> dict:
    """
    Watch for file changes or take snapshots.
    
    Args:
        directory: Directory to watch
        extensions: File extensions to watch (comma-separated)
        duration: Watch duration in seconds (0 = snapshot only)
        exclude_dirs: Directories to exclude
        snapshot: Take snapshot only (no watching)
        compare_snapshot: Path to previous snapshot to compare
        
    Returns:
        dict with 'success', 'data' (events or snapshot) or 'error'
    """
    args = ["-dir", directory]
    
    if extensions:
        args.extend(["-ext", extensions])
    if duration > 0:
        args.extend(["-duration", str(duration)])
    if exclude_dirs:
        args.extend(["-exclude", exclude_dirs])
    if snapshot:
        args.append("-snapshot")
    if compare_snapshot:
        args.extend(["-since", compare_snapshot])
    
    return _run_binary("file-watcher", args, timeout=max(duration + 10, 60))


# Tool definitions for Jarvis tool registry
TOOL_DEFINITIONS = [
    {
        "name": "fast_search",
        "description": "High-performance parallel file search using Go. Much faster than Python for large codebases.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (string or regex)"
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in"
                },
                "regex": {
                    "type": "boolean",
                    "description": "Treat pattern as regex"
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case insensitive search"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File glob pattern (e.g., '*.py')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results"
                }
            },
            "required": ["pattern"]
        },
        "function": fast_search
    },
    {
        "name": "index_files",
        "description": "Fast parallel file indexing. Returns file metadata for all files in a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to index"
                },
                "with_hash": {
                    "type": "boolean",
                    "description": "Calculate MD5 hash for each file"
                },
                "extensions": {
                    "type": "string",
                    "description": "Filter by extensions (comma-separated, e.g., 'py,go,js')"
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum directory depth (-1 for unlimited)"
                },
                "exclude_dirs": {
                    "type": "string",
                    "description": "Directories to exclude (comma-separated)"
                }
            },
            "required": []
        },
        "function": index_files
    },
    {
        "name": "analyze_code",
        "description": "Analyze code structure: extract functions, classes, methods, imports from source files. Supports Python, Go, JavaScript, TypeScript.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory to analyze"
                },
                "extensions": {
                    "type": "string",
                    "description": "Filter by extensions (comma-separated, e.g., 'py,go,js')"
                },
                "symbol_type": {
                    "type": "string",
                    "description": "Filter by symbol type: function, class, method, import"
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum directory depth (-1 for unlimited)"
                }
            },
            "required": ["path"]
        },
        "function": analyze_code
    },
    {
        "name": "run_parallel",
        "description": "Run multiple commands in parallel. Great for running tests, linters, or builds on multiple files simultaneously.",
        "parameters": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "description": "List of task objects with 'id', 'command', optional 'dir'"
                },
                "command": {
                    "type": "string",
                    "description": "Command template with {file} placeholder"
                },
                "files": {
                    "type": "array",
                    "description": "List of files to run command on"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for tasks"
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Max parallel workers (0 = auto)"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout per task in seconds"
                }
            },
            "required": []
        },
        "function": run_parallel
    },
    {
        "name": "generate_diff",
        "description": "Generate a unified diff between two files.",
        "parameters": {
            "type": "object",
            "properties": {
                "old_file": {
                    "type": "string",
                    "description": "Path to the original file"
                },
                "new_file": {
                    "type": "string",
                    "description": "Path to the modified file"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context around changes"
                }
            },
            "required": ["old_file", "new_file"]
        },
        "function": generate_diff
    },
    {
        "name": "apply_diff",
        "description": "Apply a text replacement to a file. Finds exact text and replaces it.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_file": {
                    "type": "string",
                    "description": "File to modify"
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text"
                },
                "preview": {
                    "type": "boolean",
                    "description": "Preview without modifying file"
                }
            },
            "required": ["target_file", "old_text", "new_text"]
        },
        "function": apply_diff
    },
    {
        "name": "resolve_symbol",
        "description": "Find where a symbol (function, class, variable) is defined and used across the codebase.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Name of the symbol to find"
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search"
                },
                "extensions": {
                    "type": "string",
                    "description": "Filter by extensions (comma-separated)"
                },
                "find_defs": {
                    "type": "boolean",
                    "description": "Find definitions"
                },
                "find_refs": {
                    "type": "boolean",
                    "description": "Find references"
                }
            },
            "required": ["symbol_name"]
        },
        "function": resolve_symbol
    },
    {
        "name": "git_analyze",
        "description": "Analyze git repository: blame, log, diff, status, branches, commit changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Operation: blame, log, diff, status, branches, changes"
                },
                "file": {
                    "type": "string",
                    "description": "File path (for blame, log)"
                },
                "commit": {
                    "type": "string",
                    "description": "Commit hash"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of commits to show"
                },
                "since": {
                    "type": "string",
                    "description": "Show commits since date (e.g., '1 week ago')"
                },
                "author": {
                    "type": "string",
                    "description": "Filter by author"
                }
            },
            "required": ["mode"]
        },
        "function": git_analyze
    },
    {
        "name": "watch_files",
        "description": "Watch for file changes or take/compare snapshots of directory state.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to watch"
                },
                "extensions": {
                    "type": "string",
                    "description": "File extensions to watch"
                },
                "duration": {
                    "type": "integer",
                    "description": "Watch duration in seconds"
                },
                "snapshot": {
                    "type": "boolean",
                    "description": "Take snapshot only"
                },
                "compare_snapshot": {
                    "type": "string",
                    "description": "Path to previous snapshot to compare"
                }
            },
            "required": []
        },
        "function": watch_files
    }
]


# =============================================================================
# BaseTool Wrapper Classes for Auto-Discovery
# =============================================================================

# Sensitive file patterns that should not be searched/read
SENSITIVE_PATTERNS = [".env", ".ssh", ".aws", ".gnupg", "id_rsa", "id_ed25519", 
                      "credentials", "private_key", "secret", ".netrc", "token"]

def _is_sensitive_path(path: str) -> bool:
    """Check if a path contains sensitive patterns."""
    lower = path.lower()
    return any(p in lower for p in SENSITIVE_PATTERNS)

def _filter_sensitive_results(data: dict) -> dict:
    """Remove matches from sensitive files."""
    if isinstance(data, dict) and "matches" in data:
        data["matches"] = [m for m in data["matches"] if not _is_sensitive_path(m.get("file", ""))]
        data["count"] = len(data["matches"])
    return data


from tools.base import BaseTool, ToolArg, ToolResult


class GoFastSearchTool(BaseTool):
    """Fast parallel file search using Go binary."""
    
    TOOL_NAME = "go_fast_search"
    TOOL_DESCRIPTION = "High-performance parallel file search. Faster than grep for large codebases."
    TOOL_ARGS = [
        ToolArg("pattern", "string", "Search pattern (text or regex)", required=True),
        ToolArg("directory", "string", "Directory to search", required=False, default="."),
        ToolArg("regex", "boolean", "Use regex matching", required=False, default=False),
        ToolArg("ignore_case", "boolean", "Case insensitive", required=False, default=False),
        ToolArg("file_pattern", "string", "File glob (e.g., *.py)", required=False),
        ToolArg("max_results", "integer", "Max results", required=False, default=100),
    ]

    def run(self, **kwargs) -> ToolResult:
        result = fast_search(
            pattern=kwargs.get("pattern", ""),
            directory=kwargs.get("directory", "."),
            regex=kwargs.get("regex", False),
            ignore_case=kwargs.get("ignore_case", False),
            file_pattern=kwargs.get("file_pattern"),
            max_results=kwargs.get("max_results", 100),
        )
        if result.get("success"):
            # Filter out sensitive file matches
            filtered = _filter_sensitive_results(result.get("data", {}))
            return ToolResult(ok=True, tool=self.TOOL_NAME, result=filtered)
        return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.get("error"))


class GoCodeAnalyzerTool(BaseTool):
    """Analyze code structure using Go binary."""
    
    TOOL_NAME = "go_code_analyzer"
    TOOL_DESCRIPTION = "Fast code analysis: extract functions, classes, methods, imports from source files."
    TOOL_ARGS = [
        ToolArg("path", "string", "File or directory to analyze", required=True),
        ToolArg("extensions", "string", "File extensions (comma-separated)", required=False),
        ToolArg("symbol_type", "string", "Filter: function, class, method, import", required=False),
        ToolArg("max_depth", "integer", "Max directory depth", required=False, default=10),
    ]

    def run(self, **kwargs) -> ToolResult:
        result = analyze_code(
            path=kwargs.get("path", "."),
            extensions=kwargs.get("extensions"),
            symbol_type=kwargs.get("symbol_type"),
            max_depth=kwargs.get("max_depth", 10),
        )
        if result.get("success"):
            return ToolResult(ok=True, tool=self.TOOL_NAME, result=result.get("data"))
        return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.get("error"))


class GoSymbolResolverTool(BaseTool):
    """Find symbol definitions and references using Go binary."""
    
    TOOL_NAME = "go_symbol_resolver"
    TOOL_DESCRIPTION = "Find where a function, class, or variable is defined and all its usages."
    TOOL_ARGS = [
        ToolArg("symbol", "string", "Symbol name to find", required=True),
        ToolArg("directory", "string", "Directory to search", required=False, default="."),
        ToolArg("extensions", "string", "File extensions", required=False),
    ]

    def run(self, **kwargs) -> ToolResult:
        result = resolve_symbol(
            symbol=kwargs.get("symbol", ""),
            directory=kwargs.get("directory", "."),
            extensions=kwargs.get("extensions"),
        )
        if result.get("success"):
            return ToolResult(ok=True, tool=self.TOOL_NAME, result=result.get("data"))
        return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.get("error"))


class GoGitAnalyzerTool(BaseTool):
    """Git operations using Go binary."""
    
    TOOL_NAME = "go_git_analyzer"
    TOOL_DESCRIPTION = "Fast git analysis: blame, log, diff, status, branches."
    TOOL_ARGS = [
        ToolArg("mode", "string", "Operation: blame, log, diff, status, branches", required=True, 
                enum=["blame", "log", "diff", "status", "branches"]),
        ToolArg("file", "string", "File for blame/log/diff", required=False),
        ToolArg("commit", "string", "Commit hash for diff", required=False),
        ToolArg("count", "integer", "Number of commits for log", required=False, default=10),
        ToolArg("since", "string", "Date filter for log", required=False),
        ToolArg("repo", "string", "Repository path", required=False, default="."),
    ]

    def run(self, **kwargs) -> ToolResult:
        result = git_analyze(
            mode=kwargs.get("mode", "status"),
            file=kwargs.get("file"),
            commit=kwargs.get("commit"),
            count=kwargs.get("count", 10),
            since=kwargs.get("since"),
            repo=kwargs.get("repo", "."),
        )
        if result.get("success"):
            return ToolResult(ok=True, tool=self.TOOL_NAME, result=result.get("data"))
        return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.get("error"))


class GoFileWatcherTool(BaseTool):
    """File watching and snapshot using Go binary."""
    
    TOOL_NAME = "go_file_watcher"
    TOOL_DESCRIPTION = "Take directory snapshots and detect file changes."
    TOOL_ARGS = [
        ToolArg("directory", "string", "Directory to watch", required=False, default="."),
        ToolArg("extensions", "string", "File extensions to watch", required=False),
        ToolArg("snapshot", "boolean", "Take snapshot only", required=False, default=False),
        ToolArg("compare_snapshot", "string", "Path to previous snapshot", required=False),
        ToolArg("duration", "integer", "Watch duration in seconds", required=False),
    ]

    def run(self, **kwargs) -> ToolResult:
        result = watch_files(
            directory=kwargs.get("directory", "."),
            extensions=kwargs.get("extensions"),
            snapshot=kwargs.get("snapshot", False),
            compare_snapshot=kwargs.get("compare_snapshot"),
            duration=kwargs.get("duration"),
        )
        if result.get("success"):
            return ToolResult(ok=True, tool=self.TOOL_NAME, result=result.get("data"))
        return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.get("error"))


class GoDiffEngineTool(BaseTool):
    """Generate and apply diffs using Go binary."""
    
    TOOL_NAME = "go_diff_engine"
    TOOL_DESCRIPTION = "Generate unified diffs between files or apply text replacements."
    TOOL_ARGS = [
        ToolArg("mode", "string", "Operation: diff, apply, preview", required=True,
                enum=["diff", "apply", "preview"]),
        ToolArg("old_file", "string", "Old file for diff", required=False),
        ToolArg("new_file", "string", "New file for diff", required=False),
        ToolArg("target_file", "string", "File for apply/preview", required=False),
        ToolArg("old_text", "string", "Text to replace", required=False),
        ToolArg("new_text", "string", "Replacement text", required=False),
        ToolArg("context_lines", "integer", "Context lines in diff", required=False, default=3),
    ]
    IS_DESTRUCTIVE = True

    def run(self, **kwargs) -> ToolResult:
        result = generate_diff(
            mode=kwargs.get("mode", "diff"),
            old_file=kwargs.get("old_file"),
            new_file=kwargs.get("new_file"),
            context_lines=kwargs.get("context_lines", 3),
        ) if kwargs.get("mode") == "diff" else apply_diff(
            target_file=kwargs.get("target_file", ""),
            old_text=kwargs.get("old_text", ""),
            new_text=kwargs.get("new_text", ""),
            preview=kwargs.get("mode") == "preview",
        )
        if result.get("success"):
            return ToolResult(ok=True, tool=self.TOOL_NAME, result=result.get("data"))
        return ToolResult(ok=False, tool=self.TOOL_NAME, error=result.get("error"))


if __name__ == "__main__":
    # Test the bridge
    import sys
    
    print("Testing Go Bridge...")
    print()
    
    # Test fast_search
    print("=== Fast Search Test ===")
    result = fast_search("def", directory=".", file_pattern="*.py", max_results=5)
    print(json.dumps(result, indent=2))
    print()
    
    # Test index_files
    print("=== File Indexer Test ===")
    result = index_files(directory=".", extensions="py,go", max_depth=2)
    print(json.dumps(result, indent=2))
    print()
    
    # Test code analyzer
    print("=== Code Analyzer Test ===")
    result = analyze_code(path=".", extensions="py", symbol_type="function", max_depth=1)
    print(json.dumps(result, indent=2))
    print()
    
    # Test parallel runner
    print("=== Parallel Runner Test ===")
    result = run_parallel(
        command="wc -l {file}",
        files=["main.py", "config.py", "prompts.py"],
        working_dir="."
    )
    print(json.dumps(result, indent=2))
