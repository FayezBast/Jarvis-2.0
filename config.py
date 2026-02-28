"""
Jarvis-2.0 Configuration

Centralized configuration management using environment variables.
All settings are loaded from .env file or environment.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def normalize_provider(value: Optional[str]) -> str:
    """Normalize provider string to a supported value."""
    raw = (value or "").strip().lower()
    if raw in {"local", "ollama"}:
        return "ollama"
    if raw in {"gemini", "api", "cloud"}:
        return "gemini"
    return "gemini"


@dataclass
class Config:
    """Application configuration."""
    
    # Provider Configuration
    provider: str = "gemini"

    # API Configuration
    gemini_api_key: str = ""
    model_name: str = "gemini-2.5-flash"

    # Local LLM (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    local_tools_enabled: bool = True
    
    # Agent Settings
    max_iterations: int = 20
    max_retries: int = 3
    retry_delay: float = 2.0
    temperature: float = 0.0
    
    # File Operations
    max_file_chars: int = 10_000
    working_directory: str = "."
    
    # Memory
    memory_file: str = ".agent_memory.json"
    history_dir: str = ".agent_history"
    
    # Safety
    dry_run: bool = False
    verbose: bool = False


def load_config(provider_override: Optional[str] = None) -> Config:
    """Load configuration from environment variables."""
    provider = normalize_provider(provider_override or os.getenv("LLM_PROVIDER", "gemini"))
    api_key = os.getenv("GEMINI_API_KEY", "")

    if provider == "gemini" and not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found in environment. "
            "Please create a .env file with your API key."
        )

    return Config(
        provider=provider,
        gemini_api_key=api_key,
        model_name=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        local_tools_enabled=os.getenv("LOCAL_TOOLS_ENABLED", "true").lower() == "true",
        max_iterations=int(os.getenv("MAX_ITERATIONS", "20")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_delay=float(os.getenv("RETRY_DELAY", "2.0")),
        temperature=float(os.getenv("TEMPERATURE", "0.0")),
        max_file_chars=int(os.getenv("MAX_FILE_CHARS", "10000")),
        working_directory=os.getenv("WORKING_DIRECTORY", "."),
        memory_file=os.getenv("MEMORY_FILE", ".agent_memory.json"),
        history_dir=os.getenv("HISTORY_DIR", ".agent_history"),
        dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        verbose=os.getenv("VERBOSE", "false").lower() == "true",
    )


# Convenience: load config on import
_config: Optional[Config] = None


def get_config(provider_override: Optional[str] = None) -> Config:
    """Get the global configuration, loading if needed."""
    global _config
    if _config is None or (provider_override and _config.provider != normalize_provider(provider_override)):
        _config = load_config(provider_override=provider_override)
    return _config


# Legacy compatibility
MAX_FILE_CHARS = 10_000
