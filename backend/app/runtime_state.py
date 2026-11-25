"""Process-wide readiness for /health during warmup."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Status = Literal["starting", "ready", "degraded"]


@dataclass
class RuntimeState:
    status: Status = "starting"
    ready: bool = False
    detail: str = "Warming up embeddings and indexes…"
    errors: list[str] = field(default_factory=list)


RUNTIME = RuntimeState()


def mark_starting(detail: str = "Warming up embeddings and indexes…") -> None:
    RUNTIME.status = "starting"
    RUNTIME.ready = False
    RUNTIME.detail = detail


def mark_ready(detail: str = "Ready") -> None:
    RUNTIME.status = "ready"
    RUNTIME.ready = True
    RUNTIME.detail = detail
    RUNTIME.errors.clear()


def mark_degraded(detail: str, *, error: str | None = None) -> None:
    RUNTIME.status = "degraded"
    RUNTIME.ready = False
    RUNTIME.detail = detail
    if error:
        RUNTIME.errors.append(error[:400])
