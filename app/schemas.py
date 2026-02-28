"""Pydantic request/response schemas and base types."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    frequency: float = 0
    modulation: str = ""
    power: float = 0


class SignalUpdateRequest(BaseRequest):
    frequency: float | None = None
    modulation: str | None = None
    power: float | None = None
    lock_version: int = 0


class SignalResponse(BaseResponse):
    id: int
    frequency: float
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
        "frequency": signal.frequency,
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
