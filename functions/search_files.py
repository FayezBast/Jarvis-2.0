import os
import re

from google.genai import types

schema_search_files = types.FunctionDeclaration(
    name="search_files",
    description="Searches for files containing a pattern (text or regex) within a directory, returning matching lines with context",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "directory": types.Schema(
                type=types.Type.STRING,
                description="Directory to search in, relative to working directory (default: current directory)",
            ),
            "pattern": types.Schema(
                type=types.Type.STRING,
                description="Text or regex pattern to search for in file contents",
            ),
            "file_pattern": types.Schema(
                type=types.Type.STRING,
                description="Glob pattern to filter files (e.g., '*.py', '*.txt'). Default: all files",
            ),
            "is_regex": types.Schema(
                type=types.Type.BOOLEAN,
                description="Whether the pattern is a regex (default: False, treats as plain text)",
            ),
            "max_results": types.Schema(
                type=types.Type.INTEGER,
                description="Maximum number of matches to return (default: 50)",
            ),
        },
        required=["pattern"],
    ),
)


def search_files(
    working_directory,
    pattern,
    directory=".",
    file_pattern=None,
    is_regex=False,
    max_results=50,
):
    try:
        # Absolute working directory
        working_dir_abs = os.path.abspath(working_directory)

        # Build and normalize target directory
        target_dir = os.path.normpath(os.path.join(working_dir_abs, directory))

        # Guardrail: must stay inside working_directory
        valid_target = os.path.commonpath([working_dir_abs, target_dir]) == working_dir_abs
        if not valid_target:
            return f'Error: Cannot search "{directory}" as it is outside the permitted working directory'

        if not os.path.isdir(target_dir):
            return f'Error: "{directory}" is not a directory'

        # Compile pattern
        if is_regex:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return f"Error: Invalid regex pattern: {e}"
        else:
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        results = []
        files_searched = 0

        for root, dirs, files in os.walk(target_dir):
            # Skip hidden directories and common non-code directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv', '.venv')]

            for filename in files:
                # Skip hidden files
                if filename.startswith('.'):
                    continue

                # Apply file pattern filter
                if file_pattern:
                    import fnmatch
                    if not fnmatch.fnmatch(filename, file_pattern):
                        continue

                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, working_dir_abs)

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        files_searched += 1
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{rel_path}:{line_num}: {line.rstrip()[:200]}")
                                if len(results) >= max_results:
                                    results.append(f"... (truncated at {max_results} results)")
                                    return f"Searched {files_searched} files:\n" + "\n".join(results)
                except (IOError, OSError):
                    continue

        if not results:
            return f'No matches found for "{pattern}" in {files_searched} files'

        return f"Found {len(results)} matches in {files_searched} files:\n" + "\n".join(results)

    except Exception as e:
        return f"Error: {e}"
