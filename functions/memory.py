import os
import json

from google.genai import types

MEMORY_FILE = ".agent_memory.json"

schema_save_memory = types.FunctionDeclaration(
    name="save_memory",
    description="Saves a key-value pair to persistent memory. Use for remembering project context, user preferences, or important information across sessions.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "key": types.Schema(
                type=types.Type.STRING,
                description="The key to store the value under",
            ),
            "value": types.Schema(
                type=types.Type.STRING,
                description="The value to store (will be stored as string)",
            ),
        },
        required=["key", "value"],
    ),
)

schema_get_memory = types.FunctionDeclaration(
    name="get_memory",
    description="Retrieves a value from persistent memory by key, or lists all stored keys if no key is provided.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "key": types.Schema(
                type=types.Type.STRING,
                description="The key to retrieve. If not provided, lists all keys.",
            ),
        },
    ),
)

schema_delete_memory = types.FunctionDeclaration(
    name="delete_memory",
    description="Deletes a key from persistent memory.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "key": types.Schema(
                type=types.Type.STRING,
                description="The key to delete",
            ),
        },
        required=["key"],
    ),
)


def _get_memory_path(working_directory):
    return os.path.join(os.path.abspath(working_directory), MEMORY_FILE)


def _load_memory(working_directory):
    memory_path = _get_memory_path(working_directory)
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_memory_file(working_directory, memory):
    memory_path = _get_memory_path(working_directory)
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


def save_memory(working_directory, key, value):
    try:
        memory = _load_memory(working_directory)
        memory[key] = value
        _save_memory_file(working_directory, memory)
        return f'Successfully saved "{key}" to memory'
    except Exception as e:
        return f"Error saving to memory: {e}"


def get_memory(working_directory, key=None):
    try:
        memory = _load_memory(working_directory)
        
        if key is None:
            if not memory:
                return "Memory is empty"
            keys = list(memory.keys())
            return f"Stored keys ({len(keys)}): {', '.join(keys)}"
        
        if key in memory:
            return f"{key}: {memory[key]}"
        else:
            return f'Key "{key}" not found in memory'
    except Exception as e:
        return f"Error reading memory: {e}"


def delete_memory(working_directory, key):
    try:
        memory = _load_memory(working_directory)
        
        if key in memory:
            del memory[key]
            _save_memory_file(working_directory, memory)
            return f'Successfully deleted "{key}" from memory'
        else:
            return f'Key "{key}" not found in memory'
    except Exception as e:
        return f"Error deleting from memory: {e}"
