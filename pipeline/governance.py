"""Thread-safe run limits at the HTTP boundary, including failed API attempts.

No request body, API key, or response content is written to the ledger.
An unconfirmed response keeps its conservative reservation instead of becoming
zero usage. Configure once before workers; each client captures this run ledger.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
import time
from uuid import uuid4

import httpx

DEFAULT_LIMITS = {"llm": 60, "search": 24, "extract": 48, "fetch": 48,
                  "tokens": 500_000, "seconds": 1800}
_ledger = None
_task = ContextVar("evaluation_task", default="pipeline")


class BudgetExceeded(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, output_dir: Path, *, limits=None):
        self.path = Path(output_dir) / "usage.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.started = time.monotonic()
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        if any(type(v) is not int or v <= 0 for v in self.limits.values()):
            raise ValueError("All run limits must be positive integers")
        self.data = (json.loads(self.path.read_text()) if self.path.exists() else {
            "limits": self.limits, "counts": {k: 0 for k in ("llm", "search", "extract", "fetch")},
            "used_tokens": 0, "unconfirmed_tokens": 0, "elapsed_seconds": 0,
            "calls": {}, "termination_reason": None})
        if self.data["limits"] != self.limits:
            raise ValueError("Resume budget differs from the saved run")
        self.prior_seconds = self.data["elapsed_seconds"]
        # A process interrupted after reserving may already have sent its request.
        for call in self.data["calls"].values():
            if call["status"] == "running":
                call["status"] = "unconfirmed"
                self.data["unconfirmed_tokens"] += call["reserved_tokens"]
        self._save()

    def _save(self):
        self.data["elapsed_seconds"] = round(self.prior_seconds + time.monotonic() - self.started, 3)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(self.path)

    def reserve(self, kind, tokens=0, *, task_id):
        with self.lock:
            live = sum(c["reserved_tokens"] for c in self.data["calls"].values() if c["status"] == "running")
            reason = None
            if self.prior_seconds + time.monotonic() - self.started >= self.limits["seconds"]:
                reason = "wall_time_exhausted"
            elif self.data["counts"][kind] >= self.limits[kind]:
                reason = f"{kind}_attempt_limit"
            elif self.data["used_tokens"] + self.data["unconfirmed_tokens"] + live + tokens > self.limits["tokens"]:
                reason = "token_reservation_limit"
            if reason:
                self.data["termination_reason"] = reason
                self._save()
                raise BudgetExceeded(reason)
            call_id = uuid4().hex
            self.data["counts"][kind] += 1
            self.data["calls"][call_id] = {
                "call_id": call_id, "task_id": task_id, "kind": kind,
                "reserved_tokens": tokens, "actual_tokens": None, "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat()}
            self._save()
            return call_id

    def finish(self, call_id, *, tokens=None, error=None):
        with self.lock:
            call = self.data["calls"][call_id]
            if call["status"] != "running":
                raise ValueError("A call reservation can only be settled once")
            if tokens is None and call["kind"] == "llm":
                self.data["unconfirmed_tokens"] += call["reserved_tokens"]
            elif tokens is not None:
                self.data["used_tokens"] += tokens
            call.update(status="failed" if error else ("unconfirmed" if tokens is None and call["kind"] == "llm" else "finished"),
                        actual_tokens=tokens, error_type=error,
                        finished_at=datetime.now(timezone.utc).isoformat())
            self._save()

    def snapshot(self):
        with self.lock:
            self._save()
            return json.loads(json.dumps(self.data))

    def remaining_seconds(self):
        return max(0.001,self.limits["seconds"]-self.prior_seconds-(time.monotonic()-self.started))


def configure(ledger):
    global _ledger
    _ledger = ledger


@contextmanager
def task_context(task_id):
    token = _task.set(task_id)
    try:
        yield
    finally:
        _task.reset(token)


class GovernedClient(httpx.Client):
    def __init__(self, *, ledger=None, **kwargs):
        self.ledger = ledger if ledger is not None else _ledger
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        if self.ledger is None:
            return super().send(request, **kwargs)
        path = request.url.path.rstrip("/")
        kind = ("llm" if path.endswith(("/responses", "/chat/completions", "/embeddings"))
                else "search" if path.endswith("/search") else "extract" if path.endswith("/extract") else "fetch")
        tokens = 0
        if kind == "llm":
            body = json.loads(request.content)
            if path.endswith("/responses") and "max_output_tokens" not in body:
                body["max_output_tokens"] = 16_384
            if path.endswith("/chat/completions") and not any(
                    key in body for key in ("max_completion_tokens","max_tokens")):
                body["max_completion_tokens"] = 16_384
            # The conservative reservation must also be an actual wire limit.
            # Preserve authentication/timeout settings without ever logging them.
            headers = {key:value for key,value in request.headers.items() if key.lower() != "content-length"}
            request = httpx.Request(request.method,request.url,headers=headers,json=body,extensions=request.extensions)
            # UTF-8 byte length is a conservative bound for the selected BPE
            # models, available offline without downloading a tokenizer file.
            tokens = len(request.content) + int(
                body.get("max_output_tokens", body.get("max_completion_tokens", body.get("max_tokens", 16_384))))
        call_id = self.ledger.reserve(kind, tokens, task_id=_task.get())
        remaining = self.ledger.remaining_seconds()
        original = request.extensions.get("timeout",{})
        request.extensions["timeout"] = {key:min(value,remaining) if value is not None else remaining
            for key,value in {"connect":remaining,"read":remaining,"write":remaining,"pool":remaining,**original}.items()}
        try:
            response = super().send(request, **kwargs)
            actual = None
            if kind == "llm" and not kwargs.get("stream"):
                usage = response.json().get("usage", {})
                if "total_tokens" in usage:
                    actual = usage["total_tokens"]
                elif "input_tokens" in usage and "output_tokens" in usage:
                    actual = usage["input_tokens"] + usage["output_tokens"]
            self.ledger.finish(call_id, tokens=actual,
                               error=f"HTTP{response.status_code}" if response.is_error else None)
            return response
        except Exception as exc:
            self.ledger.finish(call_id, error=type(exc).__name__)
            raise


def http_client(**kwargs):
    return GovernedClient(**kwargs)


def openai_client(**kwargs):
    from openai import OpenAI
    kwargs["max_retries"] = 0
    kwargs.setdefault("timeout", 120)
    kwargs.setdefault("http_client", http_client(timeout=kwargs["timeout"]))
    return OpenAI(**kwargs)
