"""Provider abstraction — normalized data model for all AI usage sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuotaField:
    key: str
    label: str
    utilization: float       # 0–100
    resets_at: str | None


@dataclass
class UsageSnapshot:
    provider_id: str
    provider_name: str
    fields: list[QuotaField]
    error: str | None = None
    auth_error: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


class Provider(ABC):
    provider_id: str
    provider_name: str

    @abstractmethod
    def fetch(self) -> UsageSnapshot: ...

    @abstractmethod
    def is_available(self) -> bool: ...
