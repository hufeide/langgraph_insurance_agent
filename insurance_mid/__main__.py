from __future__ import annotations

import argparse
import json
from uuid import uuid4

from langgraph.types import Command

from .graph import build_graph


SCENARIOS = {
    "low": {
        "claim_id": "CLM-LOW",
        "customer_id": "customer-001",
        "tenant_id": "tenant-A",
        "claim_reason": "住院医疗费用报销，材料齐全，低风险演示。",
        "scenario": "low",
    },
    "high": {
        "claim_id": "CLM-HIGH",
        "customer_id": "customer-001",
        "tenant_id": "tenant-A",
        "claim_reason": "住院医疗费用报销，需要人工审核的高风险演示。",
        "scenario": "high",
    },
    "missing": {
        "claim_id": "CLM-MISSING",
        "customer_id": "customer-002",
        "tenant_id": "tenant-A",
        "claim_reason": "住院医疗费用报销，但缺少费用发票。",
        "scenario": "missing",
    },
    "inactive": {
        "claim_id": "CLM-INACTIVE",
        "customer_id": "customer-003",
        "tenant_id": "tenant-A",
        "claim_reason": "保单状态无效的演示。",
        "scenario": "inactive",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph 保险理赔 Agent 演示（中间件版）")
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="high",
        help="选择演示场景",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="若配置了 OPENAI_API_KEY，则使用可选的真实 LLM 分析",
    )
    args = parser.parse_args()

    initial_state = {
        **SCENARIOS[args.scenario],
        "use_llm": args.llm,
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

    graph = build_graph()
    config = {"configurable": {"thread_id": f"demo-{uuid4()}"}}

    print(f"\n=== 场景：{args.scenario} ===")
    print("开始执行工作流（中间件：审计/鉴权/追踪）……")
    result = graph.invoke(initial_state, config=config)

    snapshot = graph.get_state(config)
    if snapshot and snapshot.next:
        print("\n=== 工作流已暂停 / 等待处理 ===")
        print("下一节点：", snapshot.next)
        print("当前状态：")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        if "human_review" in snapshot.next:
            approved = input("\n模拟人工审批，输入 y 通过，其他输入拒绝：").strip().lower() == "y"
            result = graph.invoke(
                Command(
                    resume={
                        "approved": approved,
                        "reviewer_id": "demo-reviewer-001",
                    }
                ),
                config=config,
            )

    print("\n=== 最终结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
