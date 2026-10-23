from __future__ import annotations

from typing import Annotated, Any, TypedDict


def merge_unique(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Reducer: merge risk signals without duplicates, preserving order."""
    result: list[str] = []
    for value in (left or []) + (right or []):
        if value not in result:
            result.append(value)
    return result


def append_events(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Reducer: accumulate audit events across steps and concurrent node writes."""
    return (left or []) + (right or [])


class ClaimState(TypedDict, total=False):
    # Request data
    claim_id: str
    customer_id: str
    tenant_id: str
    claim_reason: str
    scenario: str

    # Results written by separate nodes
    policy_check: dict[str, Any]
    document_check: dict[str, Any]
    clause_check: dict[str, Any]
    risk_signals: Annotated[list[str], merge_unique]
    analysis: dict[str, Any]

    # Workflow status
    route: str
    review_status: str
    approval_record_id: str
    execution_result: dict[str, Any]
    final_result: str
    audit_events: Annotated[list[str], append_events]
