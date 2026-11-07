"""W5 adversarial cases for W3 replay, conflicting IDs and local checkpointing."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.world_fixture import (
    Action, Agent, TickInput, Weather, advance, create_world, verify_replay,
)
from openworld_superkernel.world_persistence import load_checkpoint, save_checkpoint


class W3HardeningTests(unittest.TestCase):
    def setUp(self):
        self.genesis = create_world(
            (Agent("alice", "owner-a", "north", 12),
             Agent("bob", "owner-b", "south", 0)),
            (("alice", "bob"),), seed=2026,
        )

    def action(self, key="id", amount=1, kind="transfer", tick=0):
        return Action(key, tick, "owner-a", "alice", "bob", kind, amount)

    def test_conflicting_payloads_same_id_are_all_rejected(self):
        commands = (self.action("shared", 1), self.action("shared", 7))
        result = advance(self.genesis, TickInput(0, commands, ()))
        self.assertEqual(result.accepted, ())
        self.assertEqual(result.rejected, (("shared", "conflicting_request_id"),
                                           ("shared", "conflicting_request_id")))
        self.assertEqual(result.world.balances, self.genesis.balances)
        self.assertTrue(verify_replay(self.genesis, result.world))

    def test_identical_retry_preserves_idempotency(self):
        command = self.action("retry", 3)
        result = advance(self.genesis, TickInput(0, (command, command), ()))
        self.assertEqual(result.accepted, ("retry",))
        self.assertEqual(result.world.balances, (("alice", 9), ("bob", 3)))

    def test_budget_above_default_has_reproducible_replay(self):
        commands = tuple(self.action(f"k{i:04d}", 0, "signal") for i in range(257))
        state = advance(self.genesis, TickInput(0, commands, ()), max_actions=300).world
        self.assertEqual(state.journal[0].action_budget, 300)
        self.assertEqual(len(state.events), 257)
        self.assertTrue(verify_replay(self.genesis, state))

    def test_budget_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            advance(self.genesis, TickInput(0, (), (), action_budget=20))

    def test_roundtrip_restart_simulation(self):
        tick0 = advance(self.genesis, TickInput(
            0, (self.action("t0", 4),), (Weather("north", "rain"),)
        )).world
        tick1 = advance(tick0, TickInput(
            1, (self.action("t1", 0, "signal", tick=1),), ()
        )).world
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "world.sqlite3"
            save_checkpoint(path, self.genesis, tick0)
            save_checkpoint(path, self.genesis, tick1)
            genesis, restored = load_checkpoint(path)
            self.assertEqual(genesis.fingerprint(), self.genesis.fingerprint())
            self.assertEqual(restored.fingerprint(), tick1.fingerprint())
            self.assertEqual(len(restored.events), 3)
            self.assertTrue(verify_replay(genesis, restored))

    def test_save_rejects_conflicting_fork_and_rolls_back(self):
        original = advance(self.genesis, TickInput(0, (self.action("a", 1),), ())).world
        fork = advance(self.genesis, TickInput(0, (self.action("b", 2),), ())).world
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "world.sqlite3"
            save_checkpoint(path, self.genesis, original)
            with self.assertRaisesRegex(ValueError, "fork history"):
                save_checkpoint(path, self.genesis, fork)
            _, restored = load_checkpoint(path)
            self.assertEqual(restored.fingerprint(), original.fingerprint())

    def test_save_rejects_inconsistent_world(self):
        from dataclasses import replace
        state = advance(self.genesis, TickInput(0, (self.action(),), ())).world
        tampered = replace(state, balances=(("alice", 999), ("bob", 0)))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "replay diverged"):
                save_checkpoint(Path(temp) / "w.sqlite3", self.genesis, tampered)

    def test_payload_tamper_detected_by_digest(self):
        state = advance(self.genesis, TickInput(0, (self.action(),), ())).world
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "w.sqlite3"
            save_checkpoint(path, self.genesis, state)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE w3_checkpoint SET payload='{}'")
            with self.assertRaisesRegex(ValueError, "corrupt"):
                load_checkpoint(path)

    def test_attacker_recomputed_digest_still_fails_replay(self):
        state = advance(self.genesis, TickInput(0, (self.action(),), ())).world
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "w.sqlite3"
            save_checkpoint(path, self.genesis, state)
            with sqlite3.connect(path) as db:
                payload = json.loads(db.execute(
                    "SELECT payload FROM w3_checkpoint"
                ).fetchone()[0])
                payload["state_fingerprint"] = "f" * 64
                serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                        separators=(",", ":"), allow_nan=False)
                digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
                db.execute("UPDATE w3_checkpoint SET payload=?, digest=?",
                           (serialized, digest))
            with self.assertRaisesRegex(ValueError, "replay diverged"):
                load_checkpoint(path)

    def test_checkpoint_with_no_external_input_is_refused(self):
        with self.assertRaisesRegex(ValueError, "external inputs missing"):
            advance(self.genesis, TickInput(0, (), None))

    def test_adversarial_invalid_action_cannot_spend(self):
        bad = self.action("spoof", 5)
        from dataclasses import replace
        result = advance(self.genesis, TickInput(
            0, (replace(bad, principal="owner-b"),), ()
        ))
        self.assertEqual(result.rejected[0][1], "unauthorized")
        self.assertEqual(result.world.balances, self.genesis.balances)


if __name__ == "__main__":
    unittest.main()
