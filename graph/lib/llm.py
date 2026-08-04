"""LiteLLM gateway chat client (OpenAI-compatible /v1 for any provider model).

The gateway accepts Claude, OpenAI, Gemini, etc. as ``model`` ids. Request
kwargs are adapted per model family so Claude is not forced through GPT-only
options (e.g. json_object mode, temperature on models that reject it).
"""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from lib.config import llm_gateway_settings

# Friendly / UI names → LiteLLM gateway model ids (same as application map).
# Unknown ids are passed through unchanged so any LiteLLM model works.
_MODEL_ALIASES: dict[str, str] = {
    "Claude 5.0 Sonnet": "claude-sonnet-5",
    "Claude 5.0 Opus": "claude-opus-5",
    "Claude 4.6 Sonnet": "claude-sonnet-4-6",
    "Claude 4.5 Sonnet": "claude-sonnet-4-5",
    "Claude Fable 5": "claude-fable-5",
    "Claude 4.8 Opus": "claude-opus-4-8",
    "Claude 4.7 Opus": "claude-opus-4-7",
    "Claude 4.6 Opus": "claude-opus-4-6",
    "Claude 4.5 Opus": "claude-opus-4-5",
    "Claude 4.5 Haiku": "claude-haiku-4-5",
    "haiku 4.5": "claude-haiku-4-5",
    "haiku-4.5": "claude-haiku-4-5",
    "OpenAI GPT 5.5": "gpt-5.5",
    "OpenAI GPT 5.4": "gpt-5.4",
    "OpenAI GPT 5.6 Sol": "gpt-5.6-sol",
    "OpenAI GPT 5.6 Terra": "gpt-5.6-terra",
    "OpenAI GPT 5.6 Luna": "gpt-5.6-luna",
}


def resolve_model_id(model: str) -> str:
    """Map UI / shorthand names to gateway ids; pass LiteLLM ids through."""
    raw = (model or "").strip()
    if not raw:
        return raw
    if raw in _MODEL_ALIASES:
        return _MODEL_ALIASES[raw]
    lower = raw.lower()
    for key, value in _MODEL_ALIASES.items():
        if key.lower() == lower:
            return value
    return raw


def _model_family(model: str) -> str:
    """Heuristic provider family for request-option adaptation."""
    m = model.lower()
    if m.startswith("claude") or "anthropic" in m or m.startswith("haiku"):
        return "claude"
    if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        return "openai"
    if m.startswith("gemini") or m.startswith("palm"):
        return "google"
    if m.startswith("command") or "cohere" in m:
        return "cohere"
    if "llama" in m or m.startswith("meta"):
        return "meta"
    if "mistral" in m or m.startswith("mixtral"):
        return "mistral"
    if "nova" in m or m.startswith("amazon"):
        return "amazon"
    return "other"


def make_client() -> tuple[OpenAI, str]:
    """Return OpenAI-compatible client pointed at LiteLLM + resolved default model."""
    gw = llm_gateway_settings()
    client = OpenAI(api_key=gw["key"], base_url=gw["base_url"])
    return client, resolve_model_id(gw["model"])


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _completion_kwargs(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None,
    use_json_object: bool,
) -> dict[str, Any]:
    """Build chat.completions kwargs safe for the target model family."""
    family = _model_family(model)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    # Newer Claude (Opus 4.8+) and some reasoning models reject temperature.
    if temperature is not None and family not in ("claude",):
        kwargs["temperature"] = temperature
    elif temperature is not None and family == "claude":
        # Older Claude via LiteLLM often accepts temperature; try only if set
        # and not a known-strict id. Prefer omitting for haiku/sonnet/opus 4.x+.
        if not re.search(r"claude-(opus|sonnet|haiku)-4", model.lower()):
            kwargs["temperature"] = temperature

    # json_object is OpenAI-oriented; Claude/others often need plain text JSON.
    if use_json_object and family == "openai":
        kwargs["response_format"] = {"type": "json_object"}

    return kwargs


def chat_json(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Call LiteLLM /v1/chat/completions and parse a JSON object response.

    ``model`` may be any LiteLLM gateway id (claude-*, gpt-*, gemini-*, …)
    or a known UI alias. Request options adapt to the provider family.
    """
    client, default_model = make_client()
    model = resolve_model_id(model or default_model)

    # Try progressively more compatible request shapes.
    attempts: list[dict[str, Any]] = [
        _completion_kwargs(model, messages, temperature=temperature, use_json_object=True),
        _completion_kwargs(model, messages, temperature=temperature, use_json_object=False),
        _completion_kwargs(model, messages, temperature=None, use_json_object=False),
    ]

    # Deduplicate identical kwargs
    seen: set[str] = set()
    unique_attempts: list[dict[str, Any]] = []
    for kwargs in attempts:
        key = json.dumps(kwargs, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique_attempts.append(kwargs)

    last_err: Exception | None = None
    resp = None
    for kwargs in unique_attempts:
        try:
            resp = client.chat.completions.create(**kwargs)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue

    if resp is None:
        assert last_err is not None
        raise last_err

    content = (resp.choices[0].message.content or "").strip()
    usage = getattr(resp, "usage", None)
    data = json.loads(_strip_fences(content))
    if not isinstance(data, dict):
        raise ValueError("LLM returned non-object JSON")
    if usage is not None:
        data.setdefault("input_tokens", getattr(usage, "prompt_tokens", 0) or 0)
        data.setdefault("output_tokens", getattr(usage, "completion_tokens", 0) or 0)
    return data
