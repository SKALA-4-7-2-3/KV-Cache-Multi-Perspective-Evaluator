from copy import deepcopy

from pipeline.worker_adapters import execute_worker, merge_role_result
import pytest
from unittest.mock import patch


def market_row(tech, criterion, value):
    return {"tech_id": tech, "criterion_id": criterion, "judgment": value}


def test_market_merge_replaces_only_active_cell():
    prior = {"result": {"assessments": [
        market_row("SW-01", "adoption", "keep-sw"),
        market_row("HW-01", "standardization", "old-hw"),
    ]}, "evidence": {"old": {"id": "old"}}}
    incoming = {"result": {"assessments": [
        market_row("SW-01", "adoption", "should-not-leak"),
        market_row("HW-01", "standardization", "new-hw"),
    ]}, "evidence": {"new": {"id": "new"}}}
    before = deepcopy(prior)
    merged = merge_role_result("market", prior, incoming, [
        {"technology_id": "HW-01", "criterion_id": "standardization"}])
    rows = {(r["tech_id"], r["criterion_id"]): r for r in merged["result"]["assessments"]}
    assert rows[("SW-01", "adoption")] == before["result"]["assessments"][0]
    assert rows[("HW-01", "standardization")]["judgment"] == "new-hw"
    assert set(merged["evidence"]) == {"old", "new"}
    assert prior == before


def test_domain_merge_preserves_untouched_criterion_exactly():
    prior = {"assessments": {"domain": {"assessments": [{"technology_id": "SW-01", "status": "completed", "criteria": [
        {"criterion_id": "capacity", "conclusion": "keep"},
        {"criterion_id": "quality", "conclusion": "old"},
    ]}]}}}
    incoming = {"assessments": {"domain": {"assessments": [{"technology_id": "SW-01", "status": "completed", "criteria": [
        {"criterion_id": "quality", "conclusion": "new"},
    ]}]}}}
    merged = merge_role_result("domain", prior, incoming, [
        {"technology_id": "SW-01", "criterion_id": "quality"}])
    assert merged["assessments"]["domain"]["assessments"][0]["criteria"] == [
        {"criterion_id": "capacity", "conclusion": "keep"},
        {"criterion_id": "quality", "conclusion": "new"},
    ]


def test_domain_merge_rejects_missing_requested_criterion():
    prior = {"assessments": {"domain": {"assessments": [{"technology_id": "SW-01", "status": "completed", "criteria": [
        {"criterion_id": "capacity", "conclusion": "keep"}]}]}}}
    incoming = {"assessments": {"domain": {"assessments": [
        {"technology_id": "SW-01", "status": "completed", "criteria": []}]}}}
    with pytest.raises(ValueError, match="omitted requested cells"):
        merge_role_result("domain", prior, incoming, [
            {"technology_id": "SW-01", "criterion_id": "capacity"}])


def test_initial_merge_rejects_missing_requested_cell_without_prior():
    incoming = {"result": {"assessments": [
        market_row("SW-01", "adoption", "present")
    ]}}
    with pytest.raises(ValueError, match="omitted requested cells"):
        merge_role_result("market", None, incoming, [
            {"technology_id": "HW-01", "criterion_id": "standardization"}])


def test_domain_merge_recomputes_status_from_full_merged_criteria():
    prior = {"assessments": {"domain": {"status": "unknown", "assessments": [
        {"technology_id": "SW-01", "status": "unknown", "criteria": [
            {"criterion_id": "capacity", "judgment": "unknown"},
            {"criterion_id": "quality", "judgment": "unknown"},
        ]}
    ]}}}
    incoming = {"assessments": {"domain": {"status": "completed", "assessments": [
        {"technology_id": "SW-01", "status": "completed", "criteria": [
            {"criterion_id": "quality", "judgment": "conditional"},
        ]}
    ]}}}
    merged = merge_role_result("domain", prior, incoming, [
        {"technology_id": "SW-01", "criterion_id": "quality"}])
    domain = merged["assessments"]["domain"]
    assert domain["status"] == "completed"
    assert domain["assessments"][0]["status"] == "completed"


def test_execute_worker_unwraps_domain_delta_and_rejects_failed_role():
    task = {"task_id": "t1", "plan_revision": 1, "role": "domain",
            "technology_ids": ["SW-01"], "criterion_ids": ["capacity"],
            "active_cells": [{"technology_id": "SW-01", "criterion_id": "capacity"}],
            "feedback": [], "operation": "assess", "dependency_ids": []}
    bundle = {"unused": True}
    with patch("pipeline.research_input.to_domain_state", return_value={}), patch(
            "pipeline.runtime.run_domain", return_value={"assessments": {"domain": {
                "status": "completed", "assessments": []}}}):
        output = execute_worker(task, bundle, {}, run_id="run", as_of="2026-10-07", model="fixture")
    assert output["assessments"]["domain"]["status"] == "completed"
    assert output["worker"]["task_id"] == "t1"
    with patch("pipeline.research_input.to_domain_state", return_value={}), patch(
            "pipeline.runtime.run_domain", return_value={"assessments": {"domain": {
                "status": "failed", "assessments": []}}}):
        with pytest.raises(RuntimeError, match="domain worker execution failed"):
            execute_worker(task, bundle, {}, run_id="run", as_of="2026-10-07", model="fixture")
