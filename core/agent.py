"""
Agent Core - The THINK → DECIDE → ACT → OBSERVE → RESPOND loop.

This is the brain of Jarvis-2.0. It:
- Manages the conversation with the AI model
- Implements the agent loop
- Handles tool execution via the dispatcher
- Maintains conversation history
"""

import os
import time
import json
import logging
import urllib.request
import urllib.error
from typing import List, Optional
from dataclasses import dataclass

from google import genai
from google.genai import types
from google.genai.errors import APIError

from tools.registry import init_tools, get_registry
from tools.dispatcher import create_dispatcher

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the agent."""
    model_name: str = "gemini-2.5-flash"
    max_iterations: int = 20
    max_retries: int = 3
    retry_delay: float = 2.0
    working_directory: str = "."
    dry_run: bool = False
    verbose: bool = False
    temperature: float = 0.0


class Agent:
    """
    The Jarvis Agent - An autonomous AI assistant.
    
    Implements the agent loop:
    1. THINK: Receive user input, consider context
    2. DECIDE: Choose to respond or use a tool
    3. ACT: Execute the tool if decided
    4. OBSERVE: Process tool results
    5. RESPOND: Provide final answer to user
    """

    def __init__(self, client: genai.Client, config: AgentConfig, system_prompt: str):
        self.client = client
        self.config = config
        self.system_prompt = system_prompt
        self.messages: List[types.Content] = []
        
        # Initialize tools
        init_tools()
        self.registry = get_registry()
        self.dispatcher = create_dispatcher(
            working_directory=config.working_directory,
            dry_run=config.dry_run,
            verbose=config.verbose,
        )
        
        logger.info(f"Agent initialized with {len(self.registry.list_tools())} tools")

    def reset(self) -> None:
        """Clear conversation history."""
        self.messages = []
        logger.info("Conversation reset")

    def process(self, user_input: str) -> str:
        """
        Process a user message through the agent loop.
        
        Args:
            user_input: The user's message
            
        Returns:
            The agent's final response
        """
        # Add user message to history
        self.messages.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )
        
        # Run the agent loop
        for iteration in range(self.config.max_iterations):
            if self.config.verbose:
                logger.info(f"Agent loop iteration {iteration + 1}")
            
            # THINK & DECIDE: Get model response
            response = self._call_model()
            
            if response is None:
                return "Error: Failed to get response from model"
            
            # Add model response to history
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content is not None:
                        self.messages.append(candidate.content)
            
            # Check if model wants to respond (no tool calls)
            if not response.function_calls:
                # RESPOND: Return final answer
                return response.text or ""
            
            # ACT & OBSERVE: Execute tool calls
            tool_responses = []
            for fc in response.function_calls:
                # Execute tool
                result = self.dispatcher.dispatch(fc)
                
                if not result.parts:
                    continue
                
                tool_responses.append(result.parts[0])
                
                if self.config.verbose:
                    fr = result.parts[0].function_response
                    if fr:
                        logger.info(f"Tool response: {fr.response}")
            
            # Feed tool responses back to model
            if tool_responses:
                self.messages.append(
                    types.Content(role="user", parts=tool_responses)
                )
        
        # Max iterations reached
        return f"Error: Reached max iterations ({self.config.max_iterations})"

    def _call_model(self) -> Optional[types.GenerateContentResponse]:
        """Call the AI model with retry logic."""
        for retry in range(self.config.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.config.model_name,
                    contents=self.messages,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        tools=[self.registry.get_function_declarations()],
                        temperature=self.config.temperature,
                    ),
                )
                
                # Log usage if verbose
                if self.config.verbose and response.usage_metadata:
                    logger.info(
                        f"Tokens - Prompt: {response.usage_metadata.prompt_token_count}, "
                        f"Response: {response.usage_metadata.candidates_token_count}"
                    )
                
                return response
                
            except APIError as e:
                if retry < self.config.max_retries - 1:
                    wait_time = self.config.retry_delay * (2 ** retry)
                    logger.warning(f"API error (attempt {retry + 1}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error after {self.config.max_retries} attempts: {e}")
                    raise
        
        return None


class LocalAgent:
    """Local LLM agent using Ollama's chat API."""

    def __init__(
        self,
        base_url: str,
        config: AgentConfig,
        system_prompt: str,
        tools_enabled: bool = True,
    ):
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.config = config
        self.system_prompt = system_prompt
        self.tools_enabled = tools_enabled
        self.messages: List[dict] = []

        init_tools()
        self.registry = get_registry()
        self.dispatcher = create_dispatcher(
            working_directory=config.working_directory,
            dry_run=config.dry_run,
            verbose=config.verbose,
        )

        self.tool_instructions = self._build_tool_instructions() if tools_enabled else ""
        logger.info("Local agent initialized (Ollama)")

    def reset(self) -> None:
        """Clear conversation history."""
        self.messages = []
        logger.info("Conversation reset")

    def process(self, user_input: str) -> str:
        """Process a user message through the agent loop."""
        self.messages.append({"role": "user", "content": user_input})

        for iteration in range(self.config.max_iterations):
            if self.config.verbose:
                logger.info(f"Local agent loop iteration {iteration + 1}")

            response_text = self._call_model()
            if response_text is None:
                return "Error: Failed to get response from local model"

            tool_calls = self._extract_tool_calls(response_text) if self.tools_enabled else []
            self.messages.append({"role": "assistant", "content": response_text})

            if not tool_calls:
                return response_text

            for call in tool_calls:
                name = call.get("name", "")
                args = call.get("args", {}) or {}
                if not name:
                    continue

                if self.config.verbose:
                    logger.info(f"Dispatching: {name}({args})")
                else:
                    print(f" → {name}")

                result = self.dispatcher.execute(name, args)
                tool_payload = json.dumps(result.to_dict())
                self.messages.append(
                    {"role": "tool", "content": tool_payload, "name": name}
                )

        return f"Error: Reached max iterations ({self.config.max_iterations})"

    def _call_model(self) -> Optional[str]:
        """Call Ollama's chat API with retry logic."""
        messages = [
            {"role": "system", "content": self.system_prompt + self.tool_instructions},
            *self.messages,
        ]

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }

        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/api/chat"

        for retry in range(self.config.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read().decode("utf-8")
                parsed = json.loads(body)
                message = parsed.get("message", {}) or {}
                return message.get("content", "") or ""
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
                if retry < self.config.max_retries - 1:
                    wait_time = self.config.retry_delay * (2 ** retry)
                    logger.warning(f"Local model error (attempt {retry + 1}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Local model error after {self.config.max_retries} attempts: {e}")
                    return None

        return None

    def _extract_tool_calls(self, text: str) -> List[dict]:
        """Extract tool calls from JSON-only responses."""
        stripped = (text or "").strip()
        if not stripped.startswith("{"):
            return []

        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return []

        if isinstance(data, dict) and "tool_call" in data:
            call = data.get("tool_call")
            if isinstance(call, dict):
                return [call]
        if isinstance(data, dict) and "tool_calls" in data:
            calls = data.get("tool_calls")
            if isinstance(calls, list):
                return [c for c in calls if isinstance(c, dict)]
        return []

    def _build_tool_instructions(self) -> str:
        """Build a compact tool instruction block for local models."""
        lines = [
            "\n\nTool Use (JSON only when calling a tool):",
            "If you need a tool, respond ONLY with:",
            '{"tool_call": {"name": "tool_name", "args": {}}}',
            "Tool results will arrive as a message with role \"tool\" and JSON content.",
            "Available tools:",
        ]

        for tool in self.registry.get_all().values():
            schema = tool.get_schema()
            props = schema.get("parameters", {}).get("properties", {})
            required = set(schema.get("parameters", {}).get("required", []))
            arg_chunks = []
            for name, info in props.items():
                arg_type = info.get("type", "string")
                req_flag = "required" if name in required else "optional"
                arg_chunks.append(f"{name}({arg_type}, {req_flag})")
            arg_line = ", ".join(arg_chunks) if arg_chunks else "no args"
            lines.append(f"- {schema.get('name')}: {schema.get('description')} | args: {arg_line}")

        lines.append("When you have the final answer, respond normally (not JSON).")
        return "\n".join(lines)


def create_agent(
    api_key: Optional[str],
    system_prompt: str,
    working_directory: str = ".",
    model_name: str = "gemini-2.5-flash",
    dry_run: bool = False,
    verbose: bool = False,
    provider: str = "gemini",
    base_url: Optional[str] = None,
    local_tools_enabled: bool = True,
    max_iterations: int = 20,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    temperature: float = 0.0,
) -> Agent:
    """
    Factory function to create a configured agent.
    
    Args:
        api_key: API key for the AI model
        system_prompt: System prompt defining agent behavior
        working_directory: Base directory for file operations
        model_name: Name of the AI model to use
        dry_run: If True, destructive operations are simulated
        verbose: If True, enable detailed logging
        provider: "gemini" or "ollama"
        base_url: Local model base URL (for Ollama)
        local_tools_enabled: Enable JSON tool calling in local mode
        max_iterations: Max agent loop iterations
        max_retries: Max retries on model errors
        retry_delay: Backoff delay for retries
        temperature: Model temperature
        
    Returns:
        Configured Agent instance
    """
    config = AgentConfig(
        model_name=model_name,
        max_iterations=max_iterations,
        max_retries=max_retries,
        retry_delay=retry_delay,
        working_directory=os.path.abspath(working_directory),
        dry_run=dry_run,
        verbose=verbose,
        temperature=temperature,
    )

    provider_norm = (provider or "gemini").strip().lower()
    if provider_norm in {"local", "ollama"}:
        return LocalAgent(
            base_url=base_url or "http://localhost:11434",
            config=config,
            system_prompt=system_prompt,
            tools_enabled=local_tools_enabled,
        )

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Gemini provider.")

    client = genai.Client(api_key=api_key)
    return Agent(client, config, system_prompt)
