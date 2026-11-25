"""One call to a chat model through OpenRouter. The key comes from .env."""

from __future__ import annotations

import os

import requests

from pitchcheck.sec import load_env

DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"
URL = "https://openrouter.ai/api/v1/chat/completions"


def chat(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 16000) -> dict:
    """Send one user message. Returns the reply text and what the call used.

    The model thinks before it answers and the thinking counts against
    max_tokens, so the limit has to leave room for both.
    """
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key or "replace-with-your-key" in key:
        raise RuntimeError("Set OPENROUTER_API_KEY in .env (see .env.example).")
    response = requests.post(
        URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "usage": {"include": True},
        },
        timeout=180,
    )
    response.raise_for_status()
    body = response.json()
    if "choices" not in body:
        raise RuntimeError(f"The model returned no answer: {body.get('error')}")
    choice = body["choices"][0]
    text = choice["message"].get("content")
    if not text:
        raise RuntimeError(
            "The model returned an empty answer "
            f"(finish reason: {choice.get('finish_reason')}, "
            f"refusal: {choice['message'].get('refusal')}, "
            f"error: {choice.get('error')}, usage: {body.get('usage')})."
        )
    return {
        "text": text,
        "model": body.get("model", model),
        "usage": body.get("usage", {}),
    }
