"""Small in-memory security/approval/payout services for demonstration only."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...]


class DemoClaimService:
    """In production, replace with server-side authorization + a real database."""

    def can_access(self, auth: AuthContext, claim: dict[str, Any]) -> bool:
        return auth.tenant_id == claim["tenant_id"] and (
            auth.user_id == claim["customer_id"]
            or "claims_reviewer" in auth.roles
        )

    def can_execute(self, auth: AuthContext, claim: dict[str, Any]) -> bool:
        return (
            auth.tenant_id == claim["tenant_id"]
            and "claims_operator" in auth.roles
        )


class DemoApprovalService:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def create_record(
        self,
        *,
        claim_id: str,
        reviewer_id: str,
        approved: bool,
        tenant_id: str,
    ) -> str:
        record_id = str(uuid4())
        with self._lock:
            self._records[record_id] = {
                "record_id": record_id,
                "claim_id": claim_id,
                "reviewer_id": reviewer_id,
                "approved": approved,
                "tenant_id": tenant_id,
            }
        return record_id

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(record_id)
            return dict(record) if record else None


class DemoPayoutService:
    """Idempotent fake execution. It does not move money."""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def execute(self, claim_id: str, idempotency_key: str) -> dict[str, Any]:
        with self._lock:
            if idempotency_key in self._results:
                return self._results[idempotency_key]

            result = {
                "claim_id": claim_id,
                "status": "simulated_success",
                "idempotency_key": idempotency_key,
                "message": "模拟业务执行成功；没有真实支付资金。",
            }
            self._results[idempotency_key] = result
            return result


claim_service = DemoClaimService()
approval_service = DemoApprovalService()
payout_service = DemoPayoutService()
