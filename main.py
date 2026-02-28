#!/usr/bin/env python3
"""
Jarvis-2.0 - A Local-First AI Assistant

This is the main entry point for Jarvis. It provides:
- Interactive multi-turn conversation mode
- Single prompt mode for scripting
- Command-line interface with various options

Usage:
    python main.py "Your prompt here"
    python main.py --interactive
    python main.py -i -w ./myproject
"""

import os
import sys
import logging
import argparse

from core.agent import create_agent
from config import get_config, normalize_provider
from prompts import system_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
def interactive_mode(agent):
    """Run the agent in interactive multi-turn mode."""
    print("=" * 60)
    print("🤖 Jarvis-2.0 - Local-First AI Assistant")
    print("=" * 60)
    print(f"Working directory: {agent.config.working_directory}")
    print("Commands: 'exit'/'quit' to exit, '/reset' to clear history, '/memory' to show memory")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("\033[94mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 👋")
            break

        if not user_input:
            continue

        # Handle special commands
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("\nGoodbye! 👋")
            break

        if user_input.lower() == '/reset':
            agent.reset()
            print("\n🗑️  Conversation reset.\n")
            continue

        if user_input.lower() == '/memory':
            # Quick memory display
            from tools.builtin.memory_tools import _load_memory
            memory = _load_memory(agent.config.working_directory)
            if memory:
                print("\n📝 Stored Memory:")
                for k, v in memory.items():
                    print(f"  • {k}: {v[:50]}..." if len(str(v)) > 50 else f"  • {k}: {v}")
            else:
                print("\n📝 Memory is empty.")
            print()
            continue

        if user_input.lower() == '/help':
            print("\n📖 Commands:")
            print("  /reset  - Clear conversation history")
            print("  /memory - Show stored memory")
            print("  /help   - Show this help")
            print("  exit    - Quit Jarvis")
            print()
            continue

        # Process the user input
        print()
        try:
            response = agent.process(user_input)
            print(f"\033[92mJarvis:\033[0m {response}")
        except Exception as e:
            logger.exception("Error processing request")
            print(f"\033[91mError:\033[0m {e}")
        print()


def single_prompt_mode(agent, prompt: str):
    """Run the agent with a single prompt."""
    response = agent.process(prompt)
    print("Final response:")
    print(response)


def main():
    parser = argparse.ArgumentParser(
        description="Jarvis-2.0 - A Local-First AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "List all Python files"
  python main.py --interactive --working-dir ./myproject
  python main.py "Create a hello.py" --dry-run
        """
    )
    parser.add_argument("user_prompt", type=str, nargs="?", help="User prompt (optional if --interactive)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run in interactive multi-turn mode")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-w", "--working-dir", type=str, default=".", help="Working directory for file operations")
    parser.add_argument("--dry-run", action="store_true", help="Preview write operations without executing them")
    parser.add_argument("--provider", type=str, default=None, choices=["gemini", "ollama", "local"], help="LLM provider: gemini (API) or ollama (local)")
    parser.add_argument("--model", type=str, default=None, help="Model to use")
    parser.add_argument("--ollama-url", type=str, default=None, help="Ollama base URL (default from .env)")
    parser.add_argument("--ollama-model", type=str, default=None, help="Ollama model name (default from .env)")
    args = parser.parse_args()

    # Load configuration (provider-aware)
    try:
        config = get_config(provider_override=args.provider)
    except RuntimeError as e:
        print(f"Configuration error: {e}")
        print("Tip: set LLM_PROVIDER=ollama or pass --provider ollama for local mode.")
        sys.exit(1)

    provider = normalize_provider(args.provider or config.provider)
    model_name = args.model
    if not model_name:
        model_name = config.model_name if provider == "gemini" else config.ollama_model
    if provider == "ollama" and args.ollama_model:
        model_name = args.ollama_model

    ollama_url = args.ollama_url or config.ollama_base_url

    # Validate arguments
    if not args.interactive and not args.user_prompt:
        parser.error("Either provide a user_prompt or use --interactive mode")

    # Create the agent
    agent = create_agent(
        api_key=config.gemini_api_key if provider == "gemini" else None,
        system_prompt=system_prompt,
        working_directory=os.path.abspath(args.working_dir),
        model_name=model_name,
        dry_run=args.dry_run,
        verbose=args.verbose,
        provider=provider,
        base_url=ollama_url,
        local_tools_enabled=config.local_tools_enabled,
        max_iterations=config.max_iterations,
        max_retries=config.max_retries,
        retry_delay=config.retry_delay,
        temperature=config.temperature,
    )

    if args.interactive:
        interactive_mode(agent)
    else:
        single_prompt_mode(agent, args.user_prompt)


if __name__ == "__main__":
    main()
