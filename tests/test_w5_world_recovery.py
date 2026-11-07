"""W5 process-level recovery tests for *simulated* W3 SQLite worlds.

These tests demonstrate clean process termination and rollback of an unfinished
SQLite transaction. They DO NOT simulate sudden physical power loss or provide
authenticated proof of history.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_fixture import (
    Action, Agent, TickInput, advance, create_world, verify_replay,
)
from openworld_superkernel.world_persistence import load_checkpoint, save_checkpoint


class WorldRecoveryProcessTests(unittest.TestCase):
    def setUp(self):
        self.genesis = create_world(
            tuple(Agent(f"a{i}", f"owner-{i}", "north" if i < 3 else "south", 10)
                  for i in range(5)),
            tuple((f"a{i}", f"a{i + 1}") for i in range(4)), seed=2026,
        )
        first = Action("initial", 0, "owner-0", "a0", "a1", "signal")
        self.world = advance(self.genesis, TickInput(0, (first,), ())).world
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "world.sqlite"
        save_checkpoint(self.path, self.genesis, self.world)
        self.env = os.environ.copy()
        src = str(Path(__file__).resolve().parents[1] / "src")
        self.env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (src, self.env.get("PYTHONPATH", "")))
        )

    def python(self, script, *args, timeout=20):
        return subprocess.run(
            [sys.executable, "-c", script, *(str(x) for x in args)],
            env=self.env, capture_output=True, text=True, timeout=timeout,
            check=False,
        )

    def test_new_process_recovers_exact_simulated_state(self):
        code = """
import json,sys
from openworld_superkernel.world_persistence import load_checkpoint
from openworld_superkernel.world_fixture import verify_replay
g,w = load_checkpoint(sys.argv[1])
print(json.dumps({'valid':verify_replay(g,w),'fingerprint':w.fingerprint(),
                  'provenance':sorted({e.provenance for e in w.events})}))
"""
        result = self.python(code, self.path)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout)
        self.assertTrue(state["valid"])
        self.assertEqual(state["fingerprint"], self.world.fingerprint())
        self.assertEqual(state["provenance"], ["SIMULATED"])

    def test_uncommitted_process_exit_rolls_back_sqlite(self):
        code = """
import os,sqlite3,sys
db=sqlite3.connect(sys.argv[1])
db.execute('PRAGMA journal_mode=WAL')
db.execute('BEGIN IMMEDIATE')
db.execute("UPDATE w3_checkpoint SET payload='{}'")
os._exit(17)
"""
        child = self.python(code, self.path)
        self.assertEqual(child.returncode, 17, child.stderr)
        restored_genesis, restored = load_checkpoint(self.path)
        self.assertTrue(verify_replay(restored_genesis, restored))
        self.assertEqual(restored.fingerprint(), self.world.fingerprint())

    def test_two_processes_conflicting_forks_cannot_both_commit(self):
        # Each worker reads the SAME parent, then waits on a file barrier.
        # This tests SQLite serialization and the journal-prefix CAS-like check.
        script = """
import sys,time
from pathlib import Path
from openworld_superkernel.world_persistence import load_checkpoint,save_checkpoint
from openworld_superkernel.world_fixture import Action,TickInput,advance
db,key,ready,release=sys.argv[1:]
g,w=load_checkpoint(db)
a=Action(key,w.tick,'owner-0','a0','a1','signal')
next_world=advance(w,TickInput(w.tick,(a,),())).world
Path(ready).write_text('prepared')
deadline=time.monotonic()+12
while not Path(release).exists():
    if time.monotonic()>deadline:
        sys.exit(90)
    time.sleep(0.01)
try:
    save_checkpoint(db,g,next_world)
except ValueError as ex:
    if 'fork history' in str(ex):
        sys.exit(11)
    raise
"""
        release = Path(self.tmp.name) / "release"
        children = []
        ready = []
        try:
            for i in range(2):
                marker = Path(self.tmp.name) / f"ready-{i}"
                ready.append(marker)
                children.append(subprocess.Popen(
                    [sys.executable, "-c", script, str(self.path),
                     f"fork-{i}", str(marker), str(release)],
                    env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True,
                ))
            deadline = time.monotonic() + 12
            while not all(m.exists() for m in ready):
                if time.monotonic() > deadline or any(p.poll() is not None for p in children):
                    self.fail("workers failed to prepare the same parent state")
                time.sleep(0.01)
            release.touch()
            reports = [p.communicate(timeout=20) for p in children]
            codes = sorted(p.returncode for p in children)
            self.assertEqual(codes, [0, 11], reports)
            genesis, state = load_checkpoint(self.path)
            self.assertTrue(verify_replay(genesis, state))
            self.assertEqual(state.tick, 2)
            latest = state.journal[-1].actions[0].request_id
            self.assertIn(latest, {"fork-0", "fork-1"})
        finally:
            release.touch()
            for p in children:
                if p.poll() is None:
                    p.kill()
                p.communicate()

    def test_sqlite_backup_restore_is_state_equivalent(self):
        backup = Path(self.tmp.name) / "copy.sqlite"
        with sqlite3.connect(self.path) as source:
            with sqlite3.connect(backup) as destination:
                source.backup(destination)
        genesis, restored = load_checkpoint(backup)
        self.assertEqual(genesis.fingerprint(), self.genesis.fingerprint())
        self.assertEqual(restored.fingerprint(), self.world.fingerprint())

    def test_benchmark_three_graph_shapes_have_replay(self):
        benchmark_path = Path(__file__).resolve().parents[1] / "benchmarks"
        sys.path.insert(0, str(benchmark_path))
        try:
            from w5_world_recovery import measure
            for shape in ("chain", "hub", "disconnected"):
                with self.subTest(shape=shape):
                    report = measure(6, 3, 3101, shape)
                    self.assertTrue(report["replay_match"])
                    self.assertEqual(report["journal_ticks"], 3)
                    self.assertEqual(report["agent_count"], 6)
                    self.assertGreater(report["checkpoint_disk_bytes_including_wal_shm"], 0)
        finally:
            sys.path.remove(str(benchmark_path))

    def test_revocation_not_durable_is_known_risk(self):
        # Positive demonstration of a KNOWN GAP, not a security PASS.
        key = b"synthetic evaluation secret not used outside research fixtures"
        first = CapabilityAuthority(key, issuer="demo", audience="world")
        token = first.issue(principal="alice", owner="owner-a", resource="a0",
                            action="read_world", valid_from=100, expires_at=200,
                            nonce="revoked-demo")
        first.revoke("revoked-demo")
        with self.assertRaises(PermissionError):
            first.verify(token, authenticated_principal="alice", owner="owner-a",
                         resource="a0", action="read_world", now=150)
        # Reconstructing the authority loses the in-memory revocation list.
        second = CapabilityAuthority(key, issuer="demo", audience="world")
        self.assertEqual(
            second.verify(token, authenticated_principal="alice", owner="owner-a",
                          resource="a0", action="read_world", now=150).nonce,
            "revoked-demo",
        )


if __name__ == "__main__":
    unittest.main()
