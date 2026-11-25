"""One call to a chat model through OpenRouter. The key comes from .env."""

from __future__ import annotations

import os

import requests

from pitchcheck.sec import load_env

DEFAULT_MODEL = os.environ.get("PITCHCHECK_MODEL", "google/gemini-3.8-flash")
URL = "https://openrouter.ai/api/v1/chat/completions"


def chat(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 16000,
    effort: str = "low",
    json_mode: bool = False,
) -> dict:
    """Send one user message. Returns the reply text and what the call used.

    The model thinks before it answers and the thinking counts against
    max_tokens. `effort` caps the thinking at a share of that limit ("low" is
    about a fifth), so there is always room left for the answer.
    """
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key or "replace-with-your-key" in key:
        raise RuntimeError("Set OPENROUTER_API_KEY in .env (see .env.example).")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "reasoning": {"effort": effort},
        "usage": {"include": True},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    response = requests.post(
        URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=180
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
