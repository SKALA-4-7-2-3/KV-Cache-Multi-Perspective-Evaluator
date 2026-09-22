"""Thin parent-State adapter; does not own the team's graph or reducers."""

from copy import deepcopy

from .agent import run_stakeholder


def to_state_update(output: dict) -> dict:
    """Return only this role's delta; the parent must merge dictionaries by ID/role."""
    from .json_output import StakeholderOutput
    validated = StakeholderOutput.model_validate(output).model_dump(mode="json")
    role_fields = ("round", "execution_status", "evidence_status", "result", "gaps", "follow_up_questions")
    evidence = validated.get("new_evidence", {})
    if isinstance(evidence, list):
        evidence = {item.get("id", item.get("evidence_id")): item for item in evidence}
    errors = validated.get("errors", [])
    if isinstance(errors, list):
        errors = {item.get("id", item.get("error_id")): item for item in errors}
    return {"assessments": {"stakeholders": {key: validated[key] for key in role_fields}},
            "evidence": evidence,
            "usage": {"stakeholders": validated["usage"]["used"]},
            "errors": errors}


def make_stakeholder_node(*, config=None, model=None, web=None, mode="live", paper_key="paper_analyses"):
    """Build a synchronous node for the PDF section-7 State contract.

    Parent input must contain paper_analyses (the two original objects), request,
    and run_id. Parent reducers merge assessments/usage by role and evidence/errors
    by ID; do not sum cumulative usage. Other agents' fields are not modified here.
    This is not the legacy feat/review-agent RoleResult format.
    """
    def node(state):
        settings = deepcopy(state.get("config", {}))
        budget = settings.pop("budgets", {}).get("stakeholders", {})
        usage = deepcopy(state.get("usage", {}).get("stakeholders", {}))
        payload = {"schema_version": "1.0", "run_id": state.get("run_id"), "role": "stakeholders",
                   "request": deepcopy(state.get("request", {})),
                   "paper_analyses": deepcopy(state.get(paper_key, [])),
                   "config": settings, "budget": budget, "usage": usage,
                   "round": state.get("review", {}).get("round", 0)}
        output = run_stakeholder(payload, config=config, model=model, web=web, mode=mode)
        return to_state_update(output)
    return node
