"""Paths and LiteLLM gateway settings for standalone graph pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
AGENT_WIKI = HERE.parent

DEFAULT_DB = AGENT_WIKI / "application" / "data" / "tasks.db"
DEFAULT_CORPUS = HERE / "corpus"
DEFAULT_GRAPHIFY_OUT = HERE / "graphify-out"
DEFAULT_OUT = HERE / "out"
DEFAULT_APP_CONFIG = AGENT_WIKI / "application" / "config.json"
DEFAULT_LLM_MODEL = "gpt-5.5"


def load_env() -> None:
    load_dotenv(HERE / ".env")


def _resolve(path: Path | str, *, base: Path = HERE) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def tasks_db_path() -> Path:
    load_env()
    return _resolve(os.getenv("TASKS_DB_PATH", str(DEFAULT_DB)))


def corpus_dir() -> Path:
    load_env()
    return _resolve(os.getenv("CORPUS_DIR", str(DEFAULT_CORPUS)))


def graphify_out_dir() -> Path:
    load_env()
    return _resolve(os.getenv("GRAPHIFY_OUT_DIR", str(DEFAULT_GRAPHIFY_OUT)))


def out_dir() -> Path:
    load_env()
    return _resolve(os.getenv("OUT_DIR", str(DEFAULT_OUT)))


def load_app_config() -> dict[str, Any]:
    """Load agent-wiki application/config.json only (no other repos)."""
    path = Path(os.getenv("APP_CONFIG_PATH", str(DEFAULT_APP_CONFIG))).expanduser()
    if not path.is_absolute():
        path = (AGENT_WIKI / path).resolve()
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def llm_gateway_settings() -> dict[str, str]:
    """LiteLLM: application/config.json first, then graph/.env fallback."""
    load_env()
    cfg = load_app_config()

    cfg_url = (cfg.get("llm_gateway_url") or "").strip().rstrip("/")
    cfg_key = (cfg.get("llm_gateway_key") or "").strip()

    env_url = (os.getenv("LLM_GATEWAY_URL") or "").strip().rstrip("/")
    env_key = (os.getenv("LLM_GATEWAY_KEY") or "").strip()

    if cfg_url and cfg_key:
        url, key, source = cfg_url, cfg_key, "application/config.json"
    elif env_url and env_key:
        url, key, source = env_url, env_key, "graph/.env"
    else:
        raise SystemExit(
            "LiteLLM gateway is not configured.\n"
            "Set llm_gateway_url / llm_gateway_key in application/config.json,\n"
            "or LLM_GATEWAY_URL / LLM_GATEWAY_KEY in graph/.env (fallback)."
        )

    model = (os.getenv("GRAPHIFY_LLM_MODEL") or DEFAULT_LLM_MODEL).strip()
    return {
        "url": url,
        "key": key,
        "base_url": f"{url}/v1",
        "model": model,
        "source": source,
    }
