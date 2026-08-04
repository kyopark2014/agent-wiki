"""OpenAI-compatible chat client via LiteLLM gateway."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from lib.config import llm_gateway_settings


def make_client() -> tuple[OpenAI, str]:
    gw = llm_gateway_settings()
    client = OpenAI(api_key=gw["key"], base_url=gw["base_url"])
    return client, gw["model"]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def chat_json(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 1.0,
) -> dict[str, Any]:
    """Call chat/completions and parse a JSON object response."""
    client, default_model = make_client()
    model = model or default_model

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    # Prefer JSON mode when the gateway/model supports it
    try:
        resp = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception as first:
        # Retry without response_format / or with temperature=1 for gpt-5.x
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=1.0,
            )
        except Exception:
            raise first from None

    content = (resp.choices[0].message.content or "").strip()
    usage = getattr(resp, "usage", None)
    data = json.loads(_strip_fences(content))
    if not isinstance(data, dict):
        raise ValueError("LLM returned non-object JSON")
    if usage is not None:
        data.setdefault("input_tokens", getattr(usage, "prompt_tokens", 0) or 0)
        data.setdefault("output_tokens", getattr(usage, "completion_tokens", 0) or 0)
    return data
