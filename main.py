import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

from prompts import system_prompt
from call_function import available_functions, call_function


MODEL_NAME = "gemini-2.5-flash"
MAX_ITERS = 20
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def process_prompt(client, messages, args):
    """Process a single prompt through the agent loop."""
    for iteration in range(MAX_ITERS):
        # Retry loop for API errors
        response = None
        for retry in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[available_functions],
                        temperature=0,
                    ),
                )
                break  # Success, exit retry loop
            except APIError as e:
                if retry < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (2 ** retry)  # Exponential backoff
                    logger.warning(f"API error (attempt {retry + 1}/{MAX_RETRIES}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error after {MAX_RETRIES} attempts: {e}")
                    raise

        if response is None:
            raise RuntimeError("Failed to get response from API")

        if response.usage_metadata is None:
            raise RuntimeError("Gemini API request failed: usage_metadata is None.")

        if args.verbose:
            print(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")
            print(f"Response tokens: {response.usage_metadata.candidates_token_count}")

        # 1) Add model candidates to conversation history
        if response.candidates:
            for cand in response.candidates:
                if cand.content is not None:
                    messages.append(cand.content)

        # 2) If the model is done (no tool calls), return the response
        if not response.function_calls:
            return response.text

        # 3) Execute tool calls, validate results, collect parts
        function_responses = []
        for fc in response.function_calls:
            function_call_result = call_function(
                fc,
                verbose=args.verbose,
                working_directory=args.working_dir,
                dry_run=args.dry_run
            )

            if not function_call_result.parts:
                raise RuntimeError("Tool response had no parts")

            fr = function_call_result.parts[0].function_response
            if fr is None:
                raise RuntimeError("Tool response part had no function_response")

            if fr.response is None:
                raise RuntimeError("FunctionResponse.response was None")

            function_responses.append(function_call_result.parts[0])

            if args.verbose:
                print(f"-> {function_call_result.parts[0].function_response.response}")

        # 4) Feed tool responses back into the conversation for the next iteration
        messages.append(types.Content(role="user", parts=function_responses))

    # If we got here, the agent never finished
    return f"Error: Reached max iterations ({MAX_ITERS}) without producing a final response."


def interactive_mode(client, args):
    """Run the agent in interactive multi-turn mode."""
    print("=" * 60)
    print("🤖 AI Coding Agent - Interactive Mode")
    print("=" * 60)
    print(f"Working directory: {os.path.abspath(args.working_dir)}")
    print("Commands: 'exit' or 'quit' to exit, 'clear' to reset conversation")
    print("=" * 60)
    print()

    messages = []

    while True:
        try:
            user_input = input("\033[94mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 👋")
            break

        if not user_input:
            continue

        if user_input.lower() in ['exit', 'quit', 'q']:
            print("\nGoodbye! 👋")
            break

        if user_input.lower() == 'clear':
            messages = []
            print("\n🗑️  Conversation cleared.\n")
            continue

        if user_input.lower() == 'history':
            print(f"\n📜 Conversation has {len(messages)} messages.\n")
            continue

        # Add user message
        messages.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        print()
        try:
            response = process_prompt(client, messages, args)
            print(f"\033[92mAgent:\033[0m {response}")
        except Exception as e:
            print(f"\033[91mError:\033[0m {e}")
        print()


def single_prompt_mode(client, args):
    """Run the agent with a single prompt."""
    messages = [
        types.Content(role="user", parts=[types.Part(text=args.user_prompt)])
    ]

    response = process_prompt(client, messages, args)
    print("Final response:")
    print(response)


def main():
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not found in environment")

    client = genai.Client(api_key=api_key)

    parser = argparse.ArgumentParser(
        description="AI Coding Agent - A powerful assistant for coding tasks",
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
    args = parser.parse_args()

    # Validate arguments
    if not args.interactive and not args.user_prompt:
        parser.error("Either provide a user_prompt or use --interactive mode")

    if args.interactive:
        interactive_mode(client, args)
    else:
        single_prompt_mode(client, args)


if __name__ == "__main__":
    main()
