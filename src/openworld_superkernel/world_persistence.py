"""Experimental W3 SQLite checkpoint: exact inputs, rebuild-by-replay, NO trust anchor.

Do not load a database from an untrusted path. This is a CPU-only local fixture,
not an authenticated audit log, crash-consistency certification, or full server.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .world_fixture import (
    Action, Agent, TickInput, Weather, World, _input_record,
    advance, create_world, verify_replay,
)

_FORMAT = "openworld.w3.checkpoint.v1"
_KEY = "research-world"


def _canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False)


def _sha(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _manifest(genesis: World, state: World) -> dict:
    if not verify_replay(genesis, state):
        raise ValueError("world replay did not verify")
    edges = sorted((a, b) for a, adjacent in genesis.graph for b in adjacent if a < b)
    return {
        "format": _FORMAT,
        "genesis": {
            "seed": genesis.seed,
            "agents": [[a.agent_id, a.owner_id, a.region, a.resources]
                       for a in genesis.agents],
            "edges": [list(pair) for pair in edges],
            "fingerprint": genesis.fingerprint(),
        },
        "journal": [_input_record(batch) for batch in state.journal],
        "state_fingerprint": state.fingerprint(),
    }


def save_checkpoint(path: str | Path, genesis: World, state: World) -> None:
    """Replace one checkpoint atomically, rejecting stale/forked journal history.

    Checkpoints preserve complete in-memory inputs, NOT arbitrary external facts.
    File access, authentication and storage backup remain the host's job.
    """
    document = _manifest(genesis, state)
    payload = _canonical(document)
    # Round-trip through JSON before comparing the old journal prefix: Python
    # tuple records become JSON arrays (lists) when read back from SQLite.
    document = json.loads(payload)
    connection = sqlite3.connect(str(path), timeout=10)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("""CREATE TABLE IF NOT EXISTS w3_checkpoint (
            name TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL
        )""")
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute(
                "SELECT payload, digest FROM w3_checkpoint WHERE name=?", (_KEY,)
            ).fetchone()
            if old:
                if _sha(old[0]) != old[1]:
                    raise ValueError("existing checkpoint digest mismatch")
                previous = json.loads(old[0])
                if (previous.get("format") != _FORMAT
                    or previous.get("genesis") != document["genesis"]):
                    raise ValueError("checkpoint genesis mismatch")
                historical = previous.get("journal")
                if not isinstance(historical, list) or (
                    document["journal"][:len(historical)] != historical
                ):
                    raise ValueError("checkpoint would overwrite or fork history")
            connection.execute(
                "INSERT INTO w3_checkpoint (name,payload,digest) VALUES (?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET payload=excluded.payload, digest=excluded.digest",
                (_KEY, payload, _sha(payload))
            )
    finally:
        connection.close()


def load_checkpoint(path: str | Path) -> tuple[World, World]:
    """Rebuild the world from persisted *simulated* inputs, reject divergence."""
    connection = sqlite3.connect(str(path), timeout=10)
    try:
        row = connection.execute(
            "SELECT payload, digest FROM w3_checkpoint WHERE name=?", (_KEY,)
        ).fetchone()
    finally:
        connection.close()
    if row is None or _sha(row[0]) != row[1]:
        raise ValueError("checkpoint missing or corrupt")
    try:
        document = json.loads(row[0])
        if set(document) != {"format", "genesis", "journal", "state_fingerprint"}:
            raise ValueError("unsupported checkpoint fields")
        if document["format"] != _FORMAT:
            raise ValueError("unsupported checkpoint version")
        g = document["genesis"]
        if set(g) != {"seed", "agents", "edges", "fingerprint"}:
            raise ValueError("unsupported genesis fields")
        genesis = create_world(
            tuple(Agent(*record) for record in g["agents"]),
            tuple(tuple(edge) for edge in g["edges"]), seed=g["seed"]
        )
        if genesis.fingerprint() != g["fingerprint"]:
            raise ValueError("checkpoint genesis changed")
        current = genesis
        if not isinstance(document["journal"], list):
            raise ValueError("invalid checkpoint journal")
        for record in document["journal"]:
            if len(record) != 4 or record[2] is None:
                raise ValueError("incomplete tick input")
            tick, actions, weather, budget = record
            if type(budget) is not int or budget < 0:
                raise ValueError("invalid saved action budget")
            batch = TickInput(tick, tuple(Action(*a) for a in actions),
                              tuple(Weather(*e) for e in weather), budget)
            current = advance(current, batch, max_actions=budget).world
        if current.fingerprint() != document["state_fingerprint"]:
            raise ValueError("checkpoint replay diverged")
        return genesis, current
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ValueError("checkpoint has malformed records") from exc
