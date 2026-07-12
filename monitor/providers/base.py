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
    stale: bool = False


class Provider(ABC):
    provider_id: str
    provider_name: str

    @abstractmethod
    def fetch(self) -> UsageSnapshot: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    # ── Snapshot constructors (cut per-provider boilerplate) ──────────────
    def _ok(self, fields: list[QuotaField], extras: dict[str, Any] | None = None) -> UsageSnapshot:
        return UsageSnapshot(self.provider_id, self.provider_name, fields, extras=extras or {})

    def _err(self, message: str, *, auth_error: bool = False, stale: bool = False,
             fields: list[QuotaField] | None = None) -> UsageSnapshot:
        return UsageSnapshot(self.provider_id, self.provider_name, fields or [],
                             error=message, auth_error=auth_error, stale=stale)
