"""Token counting utilities using tiktoken."""

from __future__ import annotations

import tiktoken

from backend.app.config import get_settings
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_ENCODERS: dict[str, tiktoken.Encoding] = {}


def _get_encoder(model: str | None = None) -> tiktoken.Encoding:
    settings = get_settings()
    model_name = model or settings.openai_chat_model
    if model_name not in _ENCODERS:
        try:
            _ENCODERS[model_name] = tiktoken.encoding_for_model(model_name)
        except KeyError:
            _ENCODERS[model_name] = tiktoken.get_encoding("cl100k_base")
    return _ENCODERS[model_name]


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens in a text string for the given model."""
    if not text:
        return 0
    encoder = _get_encoder(model)
    return len(encoder.encode(text))


def truncate_to_token_budget(text: str, budget: int, model: str | None = None) -> str:
    """Truncate text so it fits within a token budget."""
    encoder = _get_encoder(model)
    tokens = encoder.encode(text)
    if len(tokens) <= budget:
        return text
    return encoder.decode(tokens[:budget])
