from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    RETRIEVAL_RETRY_POLICY,
    analyze_claim,
    check_documents,
    check_policy,
    execute_claim,
    finalize,
    human_review,
    request_documents,
    retrieve_clauses,
    route_after_analysis,
    route_after_policy,
    validate_input,
)
from .state import ClaimState


def build_graph(checkpointer=None):
    builder = StateGraph(ClaimState)

    builder.add_node("validate_input", validate_input)
    builder.add_node("check_policy", check_policy)
    builder.add_node("check_documents", check_documents)
    builder.add_node(
        "retrieve_clauses",
        retrieve_clauses,
        retry_policy=RETRIEVAL_RETRY_POLICY,
    )
    builder.add_node("analyze_claim", analyze_claim)
    builder.add_node("request_documents", request_documents)
    builder.add_node("human_review", human_review)
    builder.add_node("execute_claim", execute_claim)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "check_policy")

    builder.add_conditional_edges(
        "check_policy",
        route_after_policy,
        {"continue": "check_documents", "stop": "finalize"},
    )

    # Parallel branches run in the same step. The middleware writes audit_events
    # for both nodes, but the channel's append_events reducer merges them, so
    # there is no concurrent-write conflict (unlike the raw per-node writes).
    builder.add_edge("check_documents", "analyze_claim")
    builder.add_edge("check_documents", "retrieve_clauses")
    builder.add_edge("retrieve_clauses", "analyze_claim")

    builder.add_conditional_edges(
        "analyze_claim",
        route_after_analysis,
        {"missing": "request_documents", "review": "human_review", "execute": "execute_claim"},
    )

    builder.add_edge("request_documents", END)

    builder.add_conditional_edges(
        "human_review",
        lambda state: (
            "execute" if state.get("review_status") == "approved" else "finish"
        ),
        {"execute": "execute_claim", "finish": "finalize"},
    )

    builder.add_edge("execute_claim", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer or InMemorySaver())
