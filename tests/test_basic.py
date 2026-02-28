"""
Basic tests for Jarvis configuration and imports.
"""

import pytest


def test_imports():
    """Test that main modules can be imported."""
    import config
    import prompts

    assert config is not None
    assert prompts is not None


def test_config_has_required_attributes():
    """Test that config module has expected attributes."""
    import config

    # Add your config attribute checks here
    assert hasattr(config, "__file__")


def test_functions_importable():
    """Test that function modules are importable."""
    from functions import (
        delete_file,
        fetch_url,
        get_file_content,
        get_files_info,
        git_operations,
        memory,
        run_python_file,
        search_files,
        shell_command,
        write_file,
    )

    # All imports successful
    assert True


def test_core_importable():
    """Test that core modules are importable."""
    from core import agent

    assert agent is not None


def test_tools_importable():
    """Test that tools modules are importable."""
    from tools import base, dispatcher, registry

    assert base is not None
    assert dispatcher is not None
    assert registry is not None
