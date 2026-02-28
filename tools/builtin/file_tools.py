"""
File Operations Tools - Read, write, delete, search files.
"""

import os
from typing import List

from tools.base import BaseTool, ToolArg, ToolResult


class GetFilesInfoTool(BaseTool):
    """List directory contents with file information."""

    TOOL_NAME = "get_files_info"
    TOOL_DESCRIPTION = "List files and directories in the specified path with sizes and types. Use to explore project structure."
    TOOL_ARGS = [
        ToolArg(
            name="path",
            type="string",
            description="Relative path to list (default: current directory)",
            required=False,
            default=".",
        ),
        ToolArg(
            name="recursive",
            type="boolean",
            description="Whether to list recursively (default: False)",
            required=False,
            default=False,
        ),
    ]

    def run(self, working_directory: str = ".", path: str = ".", recursive: bool = False, **kwargs) -> ToolResult:
        try:
            target = os.path.join(os.path.abspath(working_directory), path)
            
            # Security check - stay within working directory
            if not os.path.abspath(target).startswith(os.path.abspath(working_directory)):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error="Path outside working directory")
            
            if not os.path.exists(target):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Path not found: {path}")
            
            files = []
            if recursive:
                for root, dirs, filenames in os.walk(target):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    
                    rel_root = os.path.relpath(root, target)
                    for name in filenames:
                        if name.startswith('.'):
                            continue
                        full_path = os.path.join(root, name)
                        rel_path = os.path.join(rel_root, name) if rel_root != "." else name
                        try:
                            size = os.path.getsize(full_path)
                            files.append({"name": rel_path, "type": "file", "size": size})
                        except OSError:
                            files.append({"name": rel_path, "type": "file", "size": 0})
                    
                    for name in dirs:
                        rel_path = os.path.join(rel_root, name) if rel_root != "." else name
                        files.append({"name": rel_path + "/", "type": "directory", "size": 0})
            else:
                for name in sorted(os.listdir(target)):
                    if name.startswith('.'):
                        continue
                    full_path = os.path.join(target, name)
                    if os.path.isdir(full_path):
                        files.append({"name": name + "/", "type": "directory", "size": 0})
                    else:
                        try:
                            size = os.path.getsize(full_path)
                            files.append({"name": name, "type": "file", "size": size})
                        except OSError:
                            files.append({"name": name, "type": "file", "size": 0})
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={"path": path, "files": files})
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class GetFileContentTool(BaseTool):
    """Read file contents."""

    TOOL_NAME = "get_file_content"
    TOOL_DESCRIPTION = "Read the contents of a file. Large files are truncated. Use for reading source code, configs, docs."
    TOOL_ARGS = [
        ToolArg(
            name="path",
            type="string",
            description="Relative path to the file to read",
            required=True,
        ),
        ToolArg(
            name="max_chars",
            type="integer",
            description="Maximum characters to return (default: 10000)",
            required=False,
            default=10000,
        ),
    ]

    # Patterns for sensitive files that should be blocked
    SENSITIVE_FILE_PATTERNS = [
        ".env",
        ".ssh",
        ".aws",
        ".gnupg",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "private_key",
        "secret",
        ".netrc",
        ".npmrc",
        "token",
    ]

    def run(self, working_directory: str = ".", path: str = "", max_chars: int = 10000, **kwargs) -> ToolResult:
        try:
            target = os.path.join(os.path.abspath(working_directory), path)
            working_dir_abs = os.path.abspath(working_directory)
            
            # ALWAYS block reading sensitive files (security protection)
            path_lower = path.lower()
            for pattern in self.SENSITIVE_FILE_PATTERNS:
                if pattern in path_lower:
                    return ToolResult(
                        ok=False, 
                        tool=self.TOOL_NAME, 
                        error=f"🔒 Access denied: Cannot read sensitive files matching '{pattern}' for security reasons"
                    )
            
            # Security check - use realpath to resolve symlinks
            real_target = os.path.realpath(target)
            if not real_target.startswith(working_dir_abs):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error="Path outside working directory (symlink detected)")
            
            if not os.path.exists(target):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"File not found: {path}")
            
            if not os.path.isfile(target):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Not a file: {path}")
            
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            
            truncated = len(content) >= max_chars
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "path": path,
                "content": content,
                "truncated": truncated,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class WriteFileTool(BaseTool):
    """Write content to a file."""

    TOOL_NAME = "write_file"
    TOOL_DESCRIPTION = "Write content to a file. Creates parent directories if needed. Overwrites existing files."
    TOOL_ARGS = [
        ToolArg(
            name="path",
            type="string",
            description="Relative path to the file to write",
            required=True,
        ),
        ToolArg(
            name="content",
            type="string",
            description="Content to write to the file",
            required=True,
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, working_directory: str = ".", path: str = "", content: str = "", **kwargs) -> ToolResult:
        try:
            working_dir_abs = os.path.abspath(working_directory)
            target = os.path.join(working_dir_abs, path)
            
            # Security check - block path traversal
            if not os.path.abspath(target).startswith(working_dir_abs):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error="Path outside working directory")
            
            # Security: Block writing to sensitive files
            dangerous_patterns = ['.env', '.ssh', '.aws', '.gnupg', 'id_rsa', '.bash', '.profile', '.zsh']
            path_lower = path.lower()
            for pattern in dangerous_patterns:
                if pattern in path_lower:
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Writing to sensitive file pattern blocked: {pattern}")
            
            # If file exists, check it's not a symlink pointing outside
            if os.path.exists(target):
                real_target = os.path.realpath(target)
                if not real_target.startswith(working_dir_abs):
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="Cannot write to symlink pointing outside working directory")
            
            # Create parent directories
            parent = os.path.dirname(target)
            if parent and not os.path.exists(parent):
                os.makedirs(parent)
            
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "path": path,
                "bytes_written": len(content.encode("utf-8")),
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class DeleteFileTool(BaseTool):
    """Delete a file."""

    TOOL_NAME = "delete_file"
    TOOL_DESCRIPTION = "Delete a file from the file system. Use with caution."
    TOOL_ARGS = [
        ToolArg(
            name="path",
            type="string",
            description="Relative path to the file to delete",
            required=True,
        ),
    ]
    IS_DESTRUCTIVE = True

    def run(self, working_directory: str = ".", path: str = "", **kwargs) -> ToolResult:
        try:
            target = os.path.join(os.path.abspath(working_directory), path)
            
            # Security check
            if not os.path.abspath(target).startswith(os.path.abspath(working_directory)):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error="Path outside working directory")
            
            if not os.path.exists(target):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"File not found: {path}")
            
            if not os.path.isfile(target):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Not a file: {path}")
            
            os.remove(target)
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={"path": path, "deleted": True})
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))


class SearchFilesTool(BaseTool):
    """Search for text patterns in files."""

    TOOL_NAME = "search_files"
    TOOL_DESCRIPTION = "Search for text or regex patterns across files. Like grep. Returns matching lines with context."
    TOOL_ARGS = [
        ToolArg(
            name="pattern",
            type="string",
            description="Text or regex pattern to search for",
            required=True,
        ),
        ToolArg(
            name="path",
            type="string",
            description="Directory or file to search in (default: current directory)",
            required=False,
            default=".",
        ),
        ToolArg(
            name="file_pattern",
            type="string",
            description="Glob pattern to filter files (e.g., '*.py')",
            required=False,
        ),
    ]

    # Sensitive file patterns to skip during search
    SENSITIVE_PATTERNS = [".env", ".ssh", ".aws", ".gnupg", "id_rsa", "id_ed25519", 
                          "credentials", "private_key", "secret", ".netrc", "token"]

    def run(self, working_directory: str = ".", pattern: str = "", path: str = ".", file_pattern: str = None, **kwargs) -> ToolResult:
        import re
        import fnmatch
        
        def is_sensitive(filepath):
            """Check if file path contains sensitive patterns."""
            lower = filepath.lower()
            return any(p in lower for p in self.SENSITIVE_PATTERNS)
        
        try:
            target = os.path.join(os.path.abspath(working_directory), path)
            
            # Security check
            if not os.path.abspath(target).startswith(os.path.abspath(working_directory)):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error="Path outside working directory")
            
            if not os.path.exists(target):
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Path not found: {path}")
            
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"Invalid regex: {e}")
            
            matches = []
            files_searched = 0
            skipped_sensitive = 0
            
            # Collect files to search
            files_to_search = []
            if os.path.isfile(target):
                if is_sensitive(target):
                    return ToolResult(ok=False, tool=self.TOOL_NAME, error="🔒 Cannot search sensitive files")
                files_to_search = [target]
            else:
                for root, dirs, filenames in os.walk(target):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for name in filenames:
                        if name.startswith('.'):
                            continue
                        full_path = os.path.join(root, name)
                        if is_sensitive(full_path):
                            skipped_sensitive += 1
                            continue
                        if file_pattern and not fnmatch.fnmatch(name, file_pattern):
                            continue
                        files_to_search.append(full_path)
            
            for file_path in files_to_search[:100]:  # Limit files
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    
                    files_searched += 1
                    rel_path = os.path.relpath(file_path, os.path.abspath(working_directory))
                    
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            matches.append({
                                "file": rel_path,
                                "line": i,
                                "text": line.rstrip()[:200],
                            })
                            
                            if len(matches) >= 50:  # Limit matches
                                break
                                
                except (IOError, UnicodeDecodeError):
                    continue
                
                if len(matches) >= 50:
                    break
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "pattern": pattern,
                "files_searched": files_searched,
                "matches": matches,
            })
            
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))
