"""Deterministic fake data sources; replace these with authorized services in production."""

POLICIES = {
    "CLM-LOW": {
        "claim_id": "CLM-LOW",
        "customer_id": "customer-001",
        "tenant_id": "tenant-A",
        "status": "active",
        "covered": True,
    },
    "CLM-HIGH": {
        "claim_id": "CLM-HIGH",
        "customer_id": "customer-001",
        "tenant_id": "tenant-A",
        "status": "active",
        "covered": True,
    },
    "CLM-MISSING": {
        "claim_id": "CLM-MISSING",
        "customer_id": "customer-002",
        "tenant_id": "tenant-A",
        "status": "active",
        "covered": True,
    },
    "CLM-INACTIVE": {
        "claim_id": "CLM-INACTIVE",
        "customer_id": "customer-003",
        "tenant_id": "tenant-A",
        "status": "inactive",
        "covered": False,
    },
}

DOCUMENTS = {
    "CLM-LOW": ["claim_form", "invoice", "discharge_summary"],
    "CLM-HIGH": ["claim_form", "invoice", "discharge_summary"],
    "CLM-MISSING": ["claim_form", "discharge_summary"],
    "CLM-INACTIVE": ["claim_form", "invoice"],
}

REQUIRED_DOCUMENTS = {"claim_form", "invoice", "discharge_summary"}

CLAUSES = [
    {
        "id": "E1",
        "title": "住院医疗费用保障",
        "text": "符合保单约定条件的住院医疗费用，可按合同约定申请报销。",
        "tenant_id": "tenant-A",
        "policy_status": "active",
    },
    {
        "id": "E2",
        "title": "费用明细要求",
        "text": "申请人应提交可核验的医疗费用明细和相关票据。",
        "tenant_id": "tenant-A",
        "policy_status": "active",
    },
    {
        "id": "E3",
        "title": "保障责任限制",
        "text": "是否属于保障范围，应结合具体保单、责任免除及其他合同约定判断。",
        "tenant_id": "tenant-A",
        "policy_status": "active",
    },
]
