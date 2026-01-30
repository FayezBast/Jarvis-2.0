import logging

from google.genai import types

# File operations
from functions.get_files_info import get_files_info, schema_get_files_info
from functions.get_file_content import get_file_content, schema_get_file_content
from functions.write_file import write_file, schema_write_file
from functions.run_python_file import run_python_file, schema_run_python_file
from functions.search_files import search_files, schema_search_files
from functions.delete_file import delete_file, schema_delete_file

# Git operations
from functions.git_operations import (
    git_status, schema_git_status,
    git_diff, schema_git_diff,
    git_log, schema_git_log,
    git_commit, schema_git_commit,
    git_branch, schema_git_branch,
)

# Web & shell
from functions.fetch_url import fetch_url, schema_fetch_url
from functions.shell_command import shell_command, schema_shell_command

# Memory & history
from functions.memory import (
    save_memory, schema_save_memory,
    get_memory, schema_get_memory,
    delete_memory, schema_delete_memory,
)
from functions.conversation_history import (
    save_conversation, schema_save_conversation,
    list_conversations, schema_list_conversations,
    load_conversation, schema_load_conversation,
)

logger = logging.getLogger(__name__)

available_functions = types.Tool(
    function_declarations=[
        # File operations
        schema_get_files_info,
        schema_get_file_content,
        schema_write_file,
        schema_run_python_file,
        schema_search_files,
        schema_delete_file,
        # Git operations
        schema_git_status,
        schema_git_diff,
        schema_git_log,
        schema_git_commit,
        schema_git_branch,
        # Web & shell
        schema_fetch_url,
        schema_shell_command,
        # Memory & history
        schema_save_memory,
        schema_get_memory,
        schema_delete_memory,
        schema_save_conversation,
        schema_list_conversations,
        schema_load_conversation,
    ],
)


def call_function(function_call, verbose=False, working_directory=".", dry_run=False):
    function_map = {
        # File operations
        "get_files_info": get_files_info,
        "get_file_content": get_file_content,
        "write_file": write_file,
        "run_python_file": run_python_file,
        "search_files": search_files,
        "delete_file": delete_file,
        # Git operations
        "git_status": git_status,
        "git_diff": git_diff,
        "git_log": git_log,
        "git_commit": git_commit,
        "git_branch": git_branch,
        # Web & shell
        "fetch_url": fetch_url,
        "shell_command": shell_command,
        # Memory & history
        "save_memory": save_memory,
        "get_memory": get_memory,
        "delete_memory": delete_memory,
        "save_conversation": save_conversation,
        "list_conversations": list_conversations,
        "load_conversation": load_conversation,
    }

    # Destructive operations that respect dry-run
    destructive_operations = [
        "write_file", "delete_file", "git_commit", "shell_command"
    ]

    function_name = function_call.name or ""

    if verbose:
        logger.info(f"Calling function: {function_name}({function_call.args})")
    else:
        print(f" - Calling function: {function_name}")

    if function_name not in function_map:
        return types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_name,
                    response={"error": f"Unknown function: {function_name}"},
                )
            ],
        )

    args = dict(function_call.args) if function_call.args else {}
    args["working_directory"] = working_directory

    # Handle dry-run for destructive operations
    if dry_run and function_name in destructive_operations:
        return types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_name,
                    response={"result": f"[DRY-RUN] Would execute {function_name} with args: {args}"},
                )
            ],
        )

    function_result = function_map[function_name](**args)

    return types.Content(
        role="tool",
        parts=[
            types.Part.from_function_response(
                name=function_name,
                response={"result": function_result},
            )
        ],
    )
