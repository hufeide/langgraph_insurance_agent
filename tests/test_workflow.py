from langgraph.types import Command

from insurance_agent.graph import build_graph


def make_state(claim_id, customer_id, scenario):
    return {
        "claim_id": claim_id,
        "customer_id": customer_id,
        "tenant_id": "tenant-A",
        "claim_reason": "测试理赔",
        "scenario": scenario,
        "use_llm": False,
        "policy_check": {},
        "document_check": {},
        "clause_check": {},
        "risk_signals": [],
        "analysis": {},
        "review_status": "pending",
        "approval_record_id": "",
        "execution_result": {},
        "final_result": "",
        "audit_events": [],
    }


def test_inactive_policy_stops():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-inactive"}}
    result = graph.invoke(
        make_state("CLM-INACTIVE", "customer-003", "inactive"),
        config=config,
    )
    assert "停止" in result["final_result"]
    assert not result.get("execution_result")


def test_missing_documents_branch():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-missing"}}
    result = graph.invoke(
        make_state("CLM-MISSING", "customer-002", "missing"),
        config=config,
    )
    assert "补充材料" in result["final_result"]
    assert not result.get("execution_result")


def test_high_risk_pauses_and_approval_resumes():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-high"}}
    first = graph.invoke(
        make_state("CLM-HIGH", "customer-001", "high"),
        config=config,
    )
    snapshot = graph.get_state(config)
    assert snapshot.next
    assert "human_review" in snapshot.next

    final = graph.invoke(
        Command(resume={"approved": True, "reviewer_id": "test-reviewer"}),
        config=config,
    )
    assert final["review_status"] == "approved"
    assert final["execution_result"]["status"] == "simulated_success"


def test_low_risk_executes_simulated_path():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-low"}}
    result = graph.invoke(
        make_state("CLM-LOW", "customer-001", "low"),
        config=config,
    )
    assert result["execution_result"]["status"] == "simulated_success"


def test_unauthorized_claim_access_is_denied():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-unauthorized"}}
    state = make_state("CLM-HIGH", "someone-else", "low")
    try:
        graph.invoke(state, config=config)
    except PermissionError:
        return
    raise AssertionError("Expected PermissionError")
