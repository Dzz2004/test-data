"""
LLM Client - OpenAI-compatible API wrapper

Reads config from .env.json, provides a simple chat interface.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from openai import OpenAI


_client: Optional[OpenAI] = None
_model: str = ""


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent.parent / ".env.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Create test-data/.env.json with:\n"
            '{"llm": {"baseUrl": "...", "apiKey": "...", "model": "..."}, "tavily": {"apiKey": "..."}}'
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_client():
    global _client, _model
    if _client is None:
        config = _load_config()
        llm_config = config["llm"]
        _client = OpenAI(
            base_url=llm_config["baseUrl"],
            api_key=llm_config["apiKey"],
        )
        _model = llm_config["model"]
    return _client, _model


def chat(messages: list, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Send a chat completion request and return the response text."""
    client, model = get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def chat_json(messages: list, temperature: float = 0.3, max_tokens: int = 4096):
    """Send a chat request expecting JSON response, parse and return."""
    text = chat(messages, temperature=temperature, max_tokens=max_tokens)
    # Extract JSON from potential markdown fences
    if "```" in text:
        import re
        match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
        if match:
            text = match.group(1)
    # Find JSON object or array
    text = text.strip()
    if not text.startswith(("{", "[")):
        import re
        match = re.search(r"[\[{][\s\S]*[\]}]", text)
        if match:
            text = match.group(0)
    return json.loads(text)
