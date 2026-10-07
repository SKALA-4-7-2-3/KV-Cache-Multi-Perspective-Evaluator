"""Persist the installed InMemorySaver's storage in a local SQLite snapshot.

Only the root's JSON controls and LangGraph Send envelopes are serializable.
No pickle or arbitrary Python imports are used. This sync saver keeps the pinned
LangGraph/checkpoint packages and needs only Python's sqlite3. It is intended for
one local run process, not distributed concurrent writers.
"""
from base64 import b64decode, b64encode
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
from threading import RLock

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Send


def _pack(value):
    if isinstance(value, Send):
        return {"kind":"send", "node":value.node, "arg":_pack(value.arg)}
    if isinstance(value, bytes):
        return {"kind":"bytes", "value":b64encode(value).decode()}
    if isinstance(value, dict):
        return {"kind":"dict", "items":[[_pack(k),_pack(v)] for k,v in value.items()]}
    if isinstance(value, (tuple,list)):
        return {"kind":"tuple" if isinstance(value,tuple) else "list", "items":[_pack(v) for v in value]}
    if value is None or type(value) in (str,int,float,bool):
        return value
    raise TypeError(f"Root checkpoint contains a non-control payload: {type(value).__name__}")


def _unpack(value):
    if not isinstance(value,dict):
        return value
    kind = value["kind"]
    if kind == "send": return Send(value["node"],_unpack(value["arg"]))
    if kind == "bytes": return b64decode(value["value"], validate=True)
    if kind == "dict": return {_unpack(k):_unpack(v) for k,v in value["items"]}
    if kind in {"tuple","list"}:
        items = [_unpack(v) for v in value["items"]]
        return tuple(items) if kind == "tuple" else items
    raise ValueError("Unknown checkpoint value type")


class ControlSerializer:
    def dumps_typed(self,value):
        return "json",json.dumps(_pack(value),ensure_ascii=False).encode()

    def loads_typed(self,value):
        kind,body = value
        if kind != "json": raise ValueError("Only JSON root checkpoint data is allowed")
        return _unpack(json.loads(body))


class SQLiteCheckpoint(InMemorySaver):
    def __init__(self,path):
        super().__init__(serde=ControlSerializer())
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.lock = RLock()
        self.connection = sqlite3.connect(str(path),check_same_thread=False)
        self.connection.execute("CREATE TABLE IF NOT EXISTS checkpoint_snapshot (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        row = self.connection.execute("SELECT payload FROM checkpoint_snapshot WHERE id=1").fetchone()
        if row:
            storage,writes,blobs = _unpack(json.loads(row[0]))
            for thread, namespaces in storage.items():
                self.storage[thread].update(namespaces)
            self.writes.update(writes)
            self.blobs.update(blobs)

    def _persist(self):
        payload = json.dumps(_pack((dict(self.storage),dict(self.writes),dict(self.blobs))),ensure_ascii=False)
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO checkpoint_snapshot (id,payload) VALUES (1,?)",(payload,))

    def put(self,*args,**kwargs):
        with self.lock:
            result = super().put(*args,**kwargs)
            self._persist()
            return result

    def put_writes(self,*args,**kwargs):
        with self.lock:
            super().put_writes(*args,**kwargs)
            self._persist()

    def close(self):
        self.connection.close()
