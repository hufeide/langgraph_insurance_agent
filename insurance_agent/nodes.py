from __future__ import annotations

import os
from typing import Any

from langgraph.types import RetryPolicy, interrupt

from .data import CLAUSES, DOCUMENTS, POLICIES, REQUIRED_DOCUMENTS
from .security import AuthContext, approval_service, claim_service, payout_service


def get_auth_context(state: dict[str, Any]) -> AuthContext:
    """Demo-only identity context. Production must inject this from trusted middleware."""
    # The CLI passes an explicit scenario identity. Never trust client-provided roles in production.
    scenario = state.get("scenario", "low")
    if scenario == "high":
        return AuthContext(
            user_id="reviewer-001",
            tenant_id="tenant-A",
            roles=("claims_reviewer", "claims_operator"),
        )
    return AuthContext(
        user_id=state.get("customer_id", "customer-001"),
        tenant_id=state.get("tenant_id", "tenant-A"),
        roles=("claims_operator",),
    )


def validate_input(state: dict[str, Any]) -> dict[str, Any]:
    claim_id = state.get("claim_id")
    if not claim_id or not isinstance(claim_id, str):
        raise ValueError("claim_id 必须是非空字符串")
    return {"audit_events": [f"validated_input:{claim_id}"]}


def check_policy(state: dict[str, Any]) -> dict[str, Any]:
    claim = POLICIES.get(state["claim_id"])
    if claim is None:
        return {
            "policy_check": {"found": False, "status": "not_found"},
            "route": "stop",
            "audit_events": ["policy_not_found"],
        }

    auth = get_auth_context(state)
    if not claim_service.can_access(auth, claim):
        raise PermissionError("当前身份无权访问该理赔案件")

    return {
        "policy_check": {
            "found": True,
            "status": claim["status"],
            "covered": claim["covered"],
            "claim_id": claim["claim_id"],
            "tenant_id": claim["tenant_id"],
        },
        "route": "continue" if claim["status"] == "active" else "stop",
        "audit_events": [f"policy_checked:{claim['status']}"],
    }


def check_documents(state: dict[str, Any]) -> dict[str, Any]:
    present = set(DOCUMENTS.get(state["claim_id"], []))
    missing = sorted(REQUIRED_DOCUMENTS - present)
    signals = ["missing_documents"] if missing else []
    return {
        "document_check": {
            "present": sorted(present),
            "missing": missing,
            "complete": not missing,
        },
        "risk_signals": signals,
        "audit_events": ["documents_checked"],
    }


def start_parallel_checks(state: ClaimState) -> dict:
    return {}
    
def retrieve_clauses(state: dict[str, Any]) -> dict[str, Any]:
    """Simulated tenant-filtered RAG. Replace with vector DB + ACL filters."""
    tenant_id = state.get("tenant_id", "tenant-A")
    policy_status = state.get("policy_check", {}).get("status")
    hits = [
        item for item in CLAUSES
        if item["tenant_id"] == tenant_id
        and policy_status == "active"
    ]
    evidence = [
        {"id": item["id"], "title": item["title"], "text": item["text"]}
        for item in hits
    ]
    return {
        "clause_check": {"evidence": evidence, "count": len(evidence)},
        "audit_events": [f"clauses_retrieved:{len(evidence)}"],
    }


def analyze_claim(state: dict[str, Any]) -> dict[str, Any]:
    """Use deterministic rules by default; optionally use an LLM for an advisory summary."""
    policy = state.get("policy_check", {})
    missing = state.get("document_check", {}).get("missing", [])
    evidence = state.get("clause_check", {}).get("evidence", [])
    scenario = state.get("scenario", "low")

    risk = "low"
    signals: list[str] = []
    if missing:
        risk = "medium"
        signals.append("incomplete_documents")
    if scenario == "high":
        risk = "high"
        signals.append("manual_review_required")
    if not policy.get("covered", False):
        risk = "high"
        signals.append("coverage_uncertain")

    summary = (
        "保单状态和条款已进入演示分析；请由有权限的审核人员核对完整合同及材料。"
    )
    if os.getenv("OPENAI_API_KEY") and state.get("use_llm"):
        try:
            from pydantic import BaseModel
            from langchain_openai import ChatOpenAI

            class AdvisoryAnalysis(BaseModel):
                summary: str
                uncertainties: list[str]
                evidence_ids: list[str]

            model = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                base_url=os.getenv("OPENAI_BASE_URL") or None,
                temperature=0,
            ).with_structured_output(AdvisoryAnalysis)

            answer = model.invoke(
                "你是保险理赔辅助分析模型，不作正式审批。只依据以下材料，"
                "明确不确定性，并引用已有证据 ID。材料："
                f"claim_reason={state.get('claim_reason', '')}; "
                f"policy={policy}; missing={missing}; evidence={evidence}"
            )
            allowed_ids = {item["id"] for item in evidence}
            valid_ids = [eid for eid in answer.evidence_ids if eid in allowed_ids]
            summary = answer.summary
            uncertainties = answer.uncertainties
            evidence_ids = valid_ids
        except ImportError as exc:
            raise RuntimeError(
                "启用 --llm 前请安装可选依赖：pip install -e '.[llm]'"
            ) from exc
    else:
        uncertainties = ["示例使用模拟规则；未进行真实合同法律判断。"]
        evidence_ids = [item["id"] for item in evidence]

    return {
        "analysis": {
            "summary": summary,
            "uncertainties": uncertainties,
            "evidence_ids": evidence_ids,
            "risk_level": risk,
        },
        "risk_signals": signals,
        "audit_events": ["claim_analyzed"],
    }


def route_after_policy(state: dict[str, Any]) -> str:
    return state.get("route", "stop")


def route_after_analysis(state: dict[str, Any]) -> str:
    missing = state.get("document_check", {}).get("missing", [])
    if missing:
        return "missing"
    if state.get("analysis", {}).get("risk_level") == "high":
        return "review"
    return "execute"


def request_documents(state: dict[str, Any]) -> dict[str, Any]:
    missing = state.get("document_check", {}).get("missing", [])
    return {
        "final_result": f"等待补充材料：{', '.join(missing)}",
        "audit_events": ["requested_missing_documents"],
    }


def human_review(state: dict[str, Any]) -> dict[str, Any]:
    """Interrupt and wait. Resume payload is a request, not a trusted approval record."""
    payload = interrupt({
        "kind": "claim_review",
        "claim_id": state["claim_id"],
        "risk_level": state.get("analysis", {}).get("risk_level"),
        "evidence": state.get("clause_check", {}).get("evidence", []),
        "message": "等待有权限的审核人员审批。演示程序会模拟审核服务。",
    })

    # This check is only a demo. Production must authenticate the reviewer out-of-band
    # and persist the official approval record in a trusted service before resuming.
    approved = payload.get("approved") is True
    reviewer_id = payload.get("reviewer_id", "demo-reviewer")
    tenant_id = state.get("tenant_id", "tenant-A")
    record_id = approval_service.create_record(
        claim_id=state["claim_id"],
        reviewer_id=reviewer_id,
        approved=approved,
        tenant_id=tenant_id,
    )
    return {
        "review_status": "approved" if approved else "rejected",
        "approval_record_id": record_id,
        "audit_events": [f"review_record_created:{record_id}"],
    }


def execute_claim(state: dict[str, Any]) -> dict[str, Any]:
    claim = POLICIES.get(state["claim_id"])
    if not claim:
        raise ValueError("理赔单不存在")

    auth = get_auth_context(state)
    if not claim_service.can_execute(auth, claim):
        raise PermissionError("当前身份无权执行理赔操作")

    if state.get("analysis", {}).get("risk_level") == "high":
        record_id = state.get("approval_record_id")
        record = approval_service.get_record(record_id) if record_id else None
        if (
            not record
            or record["claim_id"] != state["claim_id"]
            or record["tenant_id"] != claim["tenant_id"]
            or record["approved"] is not True
        ):
            raise PermissionError("缺少有效的可信审批记录")

    # Stable key for this demo; production should use a unique business operation ID.
    result = payout_service.execute(
        claim_id=state["claim_id"],
        idempotency_key=f"claim:{state['claim_id']}:payout:v1",
    )
    return {
        "execution_result": result,
        "audit_events": ["claim_execution_simulated"],
    }


def finalize(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("route") == "stop":
        result = "保单无效或未找到，流程停止。"
    elif state.get("review_status") == "rejected":
        result = "人工审核未通过，未执行赔付。"
    elif state.get("final_result"):
        result = state["final_result"]
    elif state.get("execution_result"):
        result = state["execution_result"]["message"]
    else:
        result = "流程结束；未执行赔付。"

    return {
        "final_result": result,
        "audit_events": ["workflow_finalized"],
    }


RETRIEVAL_RETRY_POLICY = RetryPolicy(max_attempts=3)
