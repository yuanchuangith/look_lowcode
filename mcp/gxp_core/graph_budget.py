"""Request-local SQL/Python work budgets with explicit incomplete results."""
from __future__ import annotations

import time
from contextvars import ContextVar
from functools import wraps


ACTIVE_BUDGET = ContextVar("business_graph_query_budget", default=None)


class GraphQueryBudgetExceeded(RuntimeError):
    pass


class QueryBudget:
    def __init__(self, seconds, vm_steps):
        self.deadline = time.monotonic() + seconds
        self.maximum = vm_steps
        self.steps = 0
        self.exceeded = False

    def progress(self):
        self.steps += 1000
        self.exceeded = self.steps >= self.maximum or time.monotonic() >= self.deadline
        return int(self.exceeded)

    def check(self):
        if self.exceeded or time.monotonic() >= self.deadline:
            self.exceeded = True
            raise GraphQueryBudgetExceeded("GRAPH_QUERY_BUDGET_EXCEEDED")


def check_query_budget():
    budget = ACTIVE_BUDGET.get()
    if budget:
        budget.check()


def bounded_graph_query(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        if ACTIVE_BUDGET.get() is not None:
            return function(self, *args, **kwargs)
        budget = QueryBudget(self.query_timeout_seconds, self.query_vm_steps)
        token = ACTIVE_BUDGET.set(budget)
        try:
            budget.check()
            return function(self, *args, **kwargs)
        except GraphQueryBudgetExceeded:
            return {"available": True, "format_version": 3, "status": "incomplete",
                "incomplete_reason": "GRAPH_QUERY_BUDGET_EXCEEDED", "operation": function.__name__,
                "scope_id": kwargs.get("scope_id") or self.scope,
                "environment": kwargs.get("environment", "development"),
                "scope_complete": False, "query_complete": False, "truncated": True,
                "matched_count": None, "matched_count_complete": False, "count": 0,
                "nodes": [], "edges": [], "evidence": [], "relations": [], "paths": [],
                "must_reverify_current_published_copy": True,
                "next_step": "The work budget ended; no complete count or isolation conclusion is available. Narrow the scope/query, or read one exact case_key snapshot."}
        finally:
            ACTIVE_BUDGET.reset(token)
    return wrapped
