"""Middleware layer for the insurance workflow.

These decorators are the LangGraph v1 equivalent of "middleware": they wrap
node functions to handle cross-cutting concerns (audit logging, authorization,
tracing) so the node implementations stay focused on business logic.

Note: LangGraph 1.x does not expose `with_listeners` on a `StateGraph`; the
idiomatic way to centralise cross-cutting behaviour on a custom graph is to
wrap the node callables, exactly as done here.
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from insurance_agent.data import POLICIES
from insurance_agent.security import AuthContext, claim_service

NodeFn = Callable[[dict[str, Any]], dict[str, Any]]


def audit_middleware(event: str | None = None) -> Callable[[NodeFn], NodeFn]:
    """Append an audit event after the wrapped node completes.

    This is the *only* place that writes ``audit_events``. Because every node's
    audit entry is produced by this single middleware, and the channel uses the
    ``append_events`` reducer, concurrent writes from parallel branches (e.g.
    ``analyze_claim`` and ``retrieve_clauses``) are merged instead of raising
    ``InvalidUpdateError``.
    """
    def decorator(fn: NodeFn) -> NodeFn:
        name = event or fn.__name__

        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            output = fn(state)
            if not isinstance(output, dict):
                return output
            events = list(output.get("audit_events", []))
            events.append(f"{name}:done")
            output["audit_events"] = events
            return output

        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


def auth_middleware(capability: str) -> Callable[[NodeFn], NodeFn]:
    """Enforce authorization before the wrapped node runs.

    capability == "access"  -> claim_service.can_access
    capability == "execute" -> claim_service.can_execute
    """
    def decorator(fn: NodeFn) -> NodeFn:
        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            claim = POLICIES.get(state.get("claim_id"))
            if claim is not None:
                if capability == "access" and not claim_service.can_access(
                    get_auth_context(state), claim
                ):
                    raise PermissionError("当前身份无权访问该理赔案件")
                if capability == "execute" and not claim_service.can_execute(
                    get_auth_context(state), claim
                ):
                    raise PermissionError("当前身份无权执行理赔操作")
            return fn(state)

        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


def trace_middleware(fn: NodeFn) -> NodeFn:
    """Optional per-node timing/logging, enabled via ``INSURANCE_MID_TRACE=1``.

    When disabled it returns the wrapped function unchanged, so it does not
    disturb any other middleware stacked around it.
    """
    if not os.getenv("INSURANCE_MID_TRACE"):
        return fn

    def wrapper(state: dict[str, Any]) -> dict[str, Any]:
        name = fn.__name__
        start = time.perf_counter()
        print(f"[trace] -> {name} start", flush=True)
        try:
            out = fn(state)
        except Exception as exc:  # noqa: BLE001 - re-raised after logging
            print(f"[trace] xx {name} raised {type(exc).__name__}: {exc}", flush=True)
            raise
        print(f"[trace] <- {name} done in {time.perf_counter() - start:.3f}s", flush=True)
        return out

    wrapper.__name__ = fn.__name__
    return wrapper


def get_auth_context(state: dict[str, Any]) -> AuthContext:
    """Demo-only identity context. Production must inject this from trusted middleware."""
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
