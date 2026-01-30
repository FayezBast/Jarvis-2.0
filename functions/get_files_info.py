import os
from google.genai import types

schema_get_files_info = types.FunctionDeclaration(
    name="get_files_info",
    description="Lists files in a specified directory relative to the working directory, providing file size and directory status",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "directory": types.Schema(
                type=types.Type.STRING,
                description="Directory path to list files from, relative to the working directory (default is the working directory itself)",
            ),
        },
    ),
)


def get_files_info(working_directory, directory="."):
    try:
        # Absolute path of the permitted working directory
        working_dir_abs = os.path.abspath(working_directory)

        # Build and normalize the target directory path
        target_dir = os.path.normpath(os.path.join(working_dir_abs, directory))

        # Guardrail: target must be inside working_directory
        valid_target_dir = os.path.commonpath([working_dir_abs, target_dir]) == working_dir_abs
        if not valid_target_dir:
            return f'Error: Cannot list "{directory}" as it is outside the permitted working directory'

        # Must be a directory
        if not os.path.isdir(target_dir):
            return f'Error: "{directory}" is not a directory'

        lines = []
        for name in os.listdir(target_dir):
            item_path = os.path.join(target_dir, name)
            is_dir = os.path.isdir(item_path)
            file_size = os.path.getsize(item_path)
            lines.append(f"- {name}: file_size={file_size} bytes, is_dir={is_dir}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error: {e}"
