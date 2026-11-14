"""Offline-safe defaults and config validation."""

from __future__ import annotations

import os

import pytest


def test_defaults_are_offline_without_env(monkeypatch):
    for key in list(os.environ.keys()):
        if key.startswith(("LLM_", "EMBEDDING_", "OPENAI_", "AZURE_", "ANTHROPIC_")):
            monkeypatch.delenv(key, raising=False)
    from backend.app.config import Settings, get_settings

    get_settings.cache_clear()
    # Ignore local .env so class defaults are what we assert
    s = Settings(_env_file=None)
    assert s.llm_provider == "extractive"
    assert s.embedding_provider == "local"
    get_settings.cache_clear()


def test_openai_without_key_raises_friendly():
    from pydantic import ValidationError

    from backend.app.config import Settings

    with pytest.raises((ValidationError, ValueError)) as exc:
        Settings(_env_file=None, llm_provider="openai", openai_api_key="")
    assert "OPENAI_API_KEY" in str(exc.value) or "openai" in str(exc.value).lower()


def test_runtime_health_fields():
    from backend.app.runtime_state import RUNTIME, mark_ready, mark_starting

    mark_starting("warming")
    assert RUNTIME.status == "starting"
    assert RUNTIME.ready is False
    mark_ready()
    assert RUNTIME.status == "ready"
    assert RUNTIME.ready is True
