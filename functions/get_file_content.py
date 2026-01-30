import os
from config import MAX_FILE_CHARS

from google.genai import types

schema_get_file_content = types.FunctionDeclaration(
    name="get_file_content",
    description="Reads the contents of a file relative to the working directory (truncates long files)",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="Path to the file to read, relative to the working directory",
            ),
        },
        required=["file_path"],
    ),
)


def get_file_content(working_directory, file_path):
    try:
        # Absolute working directory
        working_dir_abs = os.path.abspath(working_directory)

        # Build and normalize target file path
        target_path = os.path.normpath(
            os.path.join(working_dir_abs, file_path)
        )

        # Guardrail: must stay inside working_directory
        valid_target = (
            os.path.commonpath([working_dir_abs, target_path])
            == working_dir_abs
        )
        if not valid_target:
            return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'

        # Must be a regular file
        if not os.path.isfile(target_path):
            return f'Error: File not found or is not a regular file: "{file_path}"'

        # Read file (with truncation)
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_FILE_CHARS)

            # Check if truncated
            if f.read(1):
                content += f'[...File "{file_path}" truncated at {MAX_FILE_CHARS} characters]'

        return content

    except Exception as e:
        return f"Error: {e}"
