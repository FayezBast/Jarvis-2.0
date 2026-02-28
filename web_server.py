#!/usr/bin/env python3
"""
Jarvis Web UI server.

Serves a lightweight web GUI with optional voice mode and routes requests to Jarvis.
"""

import os
import argparse
from typing import Optional, Tuple

from flask import Flask, request, jsonify, send_from_directory

from config import get_config, normalize_provider
from core.agent import create_agent
from prompts import system_prompt

app = Flask(__name__, static_folder="web", static_url_path="")

APP_STATE = {
    "agent": None,
    "provider": None,
    "model": None,
    "working_dir": None,
}

WORKING_DIR = os.getcwd()


def _build_agent(provider: str, model: str, working_dir: str):
    cfg = get_config(provider_override=provider)
    provider_norm = normalize_provider(provider or cfg.provider)
    model_name = model or (cfg.model_name if provider_norm == "gemini" else cfg.ollama_model)

    return (
        create_agent(
            api_key=cfg.gemini_api_key if provider_norm == "gemini" else None,
            system_prompt=system_prompt,
            working_directory=working_dir,
            model_name=model_name,
            dry_run=cfg.dry_run,
            verbose=cfg.verbose,
            provider=provider_norm,
            base_url=cfg.ollama_base_url,
            local_tools_enabled=cfg.local_tools_enabled,
            max_iterations=cfg.max_iterations,
            max_retries=cfg.max_retries,
            retry_delay=cfg.retry_delay,
            temperature=cfg.temperature,
        ),
        provider_norm,
        model_name,
    )


def _get_agent(provider: Optional[str], model: Optional[str]) -> Tuple[object, str, str]:
    provider_norm = normalize_provider(provider or APP_STATE["provider"])
    cfg = get_config(provider_override=provider_norm)
    desired_model = model or APP_STATE["model"]
    if not desired_model:
        desired_model = cfg.model_name if provider_norm == "gemini" else cfg.ollama_model

    if (
        APP_STATE["agent"] is None
        or APP_STATE["provider"] != provider_norm
        or APP_STATE["model"] != desired_model
        or APP_STATE["working_dir"] != WORKING_DIR
    ):
        agent, provider_norm, model_name = _build_agent(provider_norm, desired_model, WORKING_DIR)
        APP_STATE.update(
            {
                "agent": agent,
                "provider": provider_norm,
                "model": model_name,
                "working_dir": WORKING_DIR,
            }
        )

    return APP_STATE["agent"], APP_STATE["provider"], APP_STATE["model"]


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/<path:path>")
def static_proxy(path: str):
    return send_from_directory("web", path)


@app.route("/api/config", methods=["GET"])
def api_config():
    cfg = get_config()
    provider = APP_STATE["provider"] or cfg.provider
    model = APP_STATE["model"] or (cfg.model_name if provider == "gemini" else cfg.ollama_model)
    return jsonify(
        {
            "provider": provider,
            "model": model,
            "providers": ["gemini", "ollama"],
            "defaults": {
                "gemini": cfg.model_name,
                "ollama": cfg.ollama_model,
            },
            "local_tools_enabled": cfg.local_tools_enabled,
        }
    )


@app.route("/api/chat", methods=["POST"])
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "Message is required."}), 400

    provider = payload.get("provider")
    model = payload.get("model")
    agent, provider_norm, model_name = _get_agent(provider, model)

    try:
        response = agent.process(message)
        return jsonify(
            {
                "ok": True,
                "response": response,
                "provider": provider_norm,
                "model": model_name,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def api_reset():
    if APP_STATE["agent"] is not None:
        APP_STATE["agent"].reset()
    return jsonify({"ok": True})


def main():
    global WORKING_DIR
    parser = argparse.ArgumentParser(description="Jarvis Web UI")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--working-dir", type=str, default=".", help="Working directory for tools")
    parser.add_argument("--provider", type=str, choices=["gemini", "ollama", "local"], default=None)
    parser.add_argument("--model", type=str, default=None, help="Model to use")
    args = parser.parse_args()

    WORKING_DIR = os.path.abspath(args.working_dir)
    cfg = get_config(provider_override=args.provider)
    provider = normalize_provider(args.provider or cfg.provider)
    model = args.model or (cfg.model_name if provider == "gemini" else cfg.ollama_model)

    agent, provider_norm, model_name = _build_agent(provider, model, WORKING_DIR)
    APP_STATE.update(
        {
            "agent": agent,
            "provider": provider_norm,
            "model": model_name,
            "working_dir": WORKING_DIR,
        }
    )

    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
