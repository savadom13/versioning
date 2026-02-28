"""Pydantic request/response schemas and base types."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


# --- Base ---


class BaseRequest(BaseModel):
    """Base for API request bodies."""
    pass


class BaseResponse(BaseModel):
    """Base for API responses."""
    pass


class ErrorResponse(BaseResponse):
    """Standard error payload."""
    error: str


# --- Auth ---


class LoginRequest(BaseRequest):
    """Login body: username + password (demo: test_user / test_pass)."""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseResponse):
    """Login success: token and user."""
    access_token: str
    user: str


# --- Session (legacy / current user) ---


class SessionResponse(BaseResponse):
    """Current user from JWT."""
    active_user: str


# --- Signals ---


class SignalCreateRequest(BaseRequest):
    frequency_from: float = 0
    frequency_to: float = 0
    modulation: str = ""
    power: float = 0

    @model_validator(mode="after")
    def frequency_range_order(self):
        if self.frequency_to < self.frequency_from:
            raise ValueError("frequency_to must be >= frequency_from")
        return self


class SignalUpdateRequest(BaseRequest):
    frequency_from: float | None = None
    frequency_to: float | None = None
    modulation: str | None = None
    power: float | None = None
    lock_version: int = 0

    @model_validator(mode="after")
    def frequency_range_order(self):
        if self.frequency_from is not None and self.frequency_to is not None:
            if self.frequency_to < self.frequency_from:
                raise ValueError("frequency_to must be >= frequency_from")
        return self


class SignalResponse(BaseResponse):
    id: int
    frequency_from: float
    frequency_to: float
    modulation: str
    power: float
    created_by: str
    updated_by: str
    lock_version: int
    updated: bool | None = None  # only on PATCH


# --- Assets ---


class AssetCreateRequest(BaseRequest):
    name: str = ""
    description: str = ""
    signal_ids: list[int] = Field(default_factory=list)


class AssetUpdateRequest(BaseRequest):
    name: str | None = None
    description: str | None = None
    signal_ids: list[int] | None = None
    lock_version: int = 0


class AssetResponse(BaseResponse):
    id: int
    name: str
    description: str
    signal_ids: list[int]
    created_by: str
    updated_by: str
    lock_version: int
    updated: bool | None = None  # only on PATCH


# --- Trash ---


class TrashItemResponse(BaseResponse):
    entity_type: str
    id: int
    name: str | None
    deleted_at: str | None
    deleted_by: str | None


# --- Changes (global history) ---


class ChangeRecordResponse(BaseResponse):
    """Single row for the changes history table."""
    date: str
    who: str
    operation: str
    entity_type: str
    entity_id: int
    what_changed: list[str]


# --- Versions ---


class VersionResponse(BaseResponse):
    id: int
    entity_type: str
    entity_id: int
    version: int
    operation: str
    snapshot: dict[str, Any]
    diff: dict[str, Any]
    hash: str
    changed_at: str | None
    changed_by: str | None


# --- Helpers: build response from ORM ---


def signal_to_response(signal, *, updated: bool | None = None) -> dict:
    return {
        "id": signal.id,
        "frequency_from": signal.frequency_from,
        "frequency_to": signal.frequency_to,
        "modulation": signal.modulation,
        "power": signal.power,
        "created_by": signal.created_by,
        "updated_by": signal.updated_by,
        "lock_version": signal.lock_version,
        "updated": updated,
    }


def asset_to_response(asset, *, updated: bool | None = None) -> dict:
    return {
        "id": asset.id,
        "name": asset.name,
        "description": asset.description,
        "signal_ids": sorted(s.id for s in asset.signals),
        "created_by": asset.created_by,
        "updated_by": asset.updated_by,
        "lock_version": asset.lock_version,
        "updated": updated,
    }


def version_to_response(v) -> dict:
    return {
        "id": v.id,
        "entity_type": v.entity_type,
        "entity_id": v.entity_id,
        "version": v.version,
        "operation": v.operation,
        "snapshot": v.snapshot,
        "diff": v.diff,
        "hash": v.hash,
        "changed_at": v.changed_at.isoformat() if v.changed_at else None,
        "changed_by": v.changed_by,
    }


def _format_change_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        return str(value)
    return str(value)


def change_record_to_response(v: "EntityVersion") -> dict:
    """Build a change record for the history table from an EntityVersion."""
    date = v.changed_at.isoformat() if v.changed_at else ""
    who = v.changed_by if v.changed_by else "—"
    what_changed: list[str] = []
    if v.operation == "update" and v.diff:
        for key, pair in v.diff.items():
            if isinstance(pair, dict) and "old" in pair and "new" in pair:
                old_s = _format_change_value(pair["old"])
                new_s = _format_change_value(pair["new"])
                if old_s != new_s:
                    what_changed.append(f"{key}: {old_s} → {new_s}")
    elif v.operation == "create" and v.snapshot:
        for key, val in v.snapshot.items():
            new_s = _format_change_value(val)
            if new_s != "—":
                what_changed.append(f"{key}: — → {new_s}")
    elif v.operation == "delete":
        what_changed.append("—")
    return {
        "date": date,
        "who": who,
        "operation": v.operation,
        "entity_type": v.entity_type,
        "entity_id": v.entity_id,
        "what_changed": what_changed,
    }
