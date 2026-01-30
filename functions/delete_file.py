import os

from google.genai import types

schema_delete_file = types.FunctionDeclaration(
    name="delete_file",
    description="Deletes a file relative to the working directory (cannot delete directories)",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="Path to the file to delete, relative to the working directory",
            ),
        },
        required=["file_path"],
    ),
)


def delete_file(working_directory, file_path):
    try:
        # Absolute working directory
        working_dir_abs = os.path.abspath(working_directory)

        # Build and normalize target path
        target_path = os.path.normpath(os.path.join(working_dir_abs, file_path))

        # Guardrail: must stay inside working_directory
        valid_target = os.path.commonpath([working_dir_abs, target_path]) == working_dir_abs
        if not valid_target:
            return f'Error: Cannot delete "{file_path}" as it is outside the permitted working directory'

        # Cannot delete directories
        if os.path.isdir(target_path):
            return f'Error: Cannot delete "{file_path}" as it is a directory (use rmdir for directories)'

        # Must exist
        if not os.path.exists(target_path):
            return f'Error: File not found: "{file_path}"'

        # Delete the file
        os.remove(target_path)

        return f'Successfully deleted "{file_path}"'

    except PermissionError:
        return f'Error: Permission denied when trying to delete "{file_path}"'
    except Exception as e:
        return f"Error: {e}"
