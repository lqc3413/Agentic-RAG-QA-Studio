from __future__ import annotations

from typing import Any, Mapping


PUBLIC_USER_ID = "public"
PUBLIC_VISIBILITY = "public"
PRIVATE_VISIBILITY = "private"


def normalize_user_id(user_id: Any = None) -> str:
    value = str(user_id or "").strip()
    return value or PUBLIC_USER_ID


def normalize_visibility(visibility: Any = None, *, user_id: Any = None) -> str:
    value = str(visibility or "").strip().lower()
    if value in {PUBLIC_VISIBILITY, PRIVATE_VISIBILITY}:
        return value

    normalized_user_id = normalize_user_id(user_id)
    if normalized_user_id == PUBLIC_USER_ID:
        return PUBLIC_VISIBILITY
    return PRIVATE_VISIBILITY


def normalize_document_id(document_id: Any = None, *, fallback: Any = None) -> str:
    value = str(document_id or "").strip()
    if value:
        return value
    fallback_value = str(fallback or "").strip()
    if not fallback_value:
        raise ValueError("document_id or fallback is required")
    return fallback_value


def build_parent_id(*, document_id: Any = None, source_stem: str, index: int) -> str:
    parent_key = str(document_id or source_stem).strip()
    return f"{parent_key}_parent_{index}"


def metadata_allows_user(metadata: Mapping[str, Any] | None, user_id: Any = None) -> bool:
    if not user_id:
        return True

    metadata = metadata or {}
    visibility = str(metadata.get("visibility") or "").strip().lower()
    owner_user_id = str(metadata.get("user_id") or "").strip()

    if visibility == PUBLIC_VISIBILITY:
        return True

    if not owner_user_id:
        return visibility != PRIVATE_VISIBILITY

    return owner_user_id == normalize_user_id(user_id)
