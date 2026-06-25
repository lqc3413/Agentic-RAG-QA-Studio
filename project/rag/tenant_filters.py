from __future__ import annotations

from qdrant_client.http import models as qmodels


def build_tenant_filter(user_id: str, *, include_legacy_public: bool = True) -> qmodels.Filter:
    user_id = str(user_id or "").strip()
    if not user_id:
        raise ValueError("user_id is required to build a tenant filter")

    should_conditions = [
        qmodels.FieldCondition(
            key="metadata.user_id",
            match=qmodels.MatchValue(value=user_id),
        ),
        qmodels.FieldCondition(
            key="metadata.visibility",
            match=qmodels.MatchValue(value="public"),
        ),
    ]

    if include_legacy_public:
        should_conditions.append(
            qmodels.Filter(
                must=[
                    qmodels.IsEmptyCondition(
                        is_empty=qmodels.PayloadField(key="metadata.user_id"),
                    ),
                    qmodels.IsEmptyCondition(
                        is_empty=qmodels.PayloadField(key="metadata.visibility"),
                    ),
                ],
            )
        )

    return qmodels.Filter(should=should_conditions)
