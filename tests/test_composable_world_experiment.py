"""Contract tests for the isolated research fixture only."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from composable_world import Arrow, Intent, World, advance, identity, replay, spawn


class CompositionalExperimentTests(unittest.TestCase):
    def setUp(self):
        self.initial = World.create({"alice": 10, "bob": 0, "eve": 1})
        self.grants = {"owner": frozenset({"alice"})}

    def test_arrow_identity_and_associativity(self):
        f = Arrow(int, int, lambda x: x + 1)
        g = Arrow(int, str, lambda x: str(x * 2))
        h = Arrow(str, int, len)
        self.assertEqual(f.then(identity(int))(3), f(3))
        self.assertEqual(identity(int).then(f)(3), f(3))
        self.assertEqual(f.then(g).then(h)(8), f.then(g.then(h))(8))

    def test_incompatible_ports_and_wrong_result(self):
        with self.assertRaises(TypeError):
            Arrow(int, str, str).then(Arrow(int, int, abs))
        with self.assertRaises(TypeError):
            Arrow(int, str, lambda x: x)(1)

    def test_genesis_is_reproducible_but_not_an_identity_authority(self):
        a = spawn("owner", "explorer", 42)
        self.assertEqual(a, spawn("owner", "explorer", 42))
        child = spawn("owner", "explorer", 43, a)
        self.assertEqual(child.parent_id, a.agent_id)
        self.assertEqual(child.generation, 1)
        self.assertNotEqual(child.agent_id, a.agent_id)

    def test_cross_owner_parent_rejected(self):
        with self.assertRaises(ValueError):
            spawn("other", "explorer", 44, spawn("owner", "explorer", 42))

    def test_valid_transfer_and_conservation(self):
        cmd = Intent("req-1", "owner", "alice", "bob", 4, 0)
        out = advance(self.initial, [cmd], self.grants)
        self.assertEqual(out.accepted, ("req-1",))
        self.assertEqual(out.world.balance("alice"), 6)
        self.assertEqual(out.world.balance("bob"), 4)
        self.assertEqual(sum(v for _, v in out.world.accounts), 11)
        self.assertEqual(out.world.events[0].provenance, "SIMULATED")

    def test_unauthorized_and_invalid_transfer_rejected(self):
        cmds = [Intent("x", "intruder", "alice", "bob", 1, 0),
                Intent("y", "owner", "alice", "bob", -1, 0)]
        out = advance(self.initial, cmds, self.grants)
        self.assertEqual(out.world.accounts, self.initial.accounts)
        self.assertEqual(len(out.rejected), 2)
        self.assertFalse(out.world.events)

    def test_conflicting_spends_are_serialized_deterministically(self):
        a = Intent("a", "owner", "alice", "bob", 7, 0)
        b = Intent("b", "owner", "alice", "eve", 7, 0)
        one = advance(self.initial, [b, a], self.grants)
        two = advance(self.initial, [a, b], self.grants)
        self.assertEqual(one.world, two.world)
        self.assertEqual(one.accepted, ("a",))
        self.assertEqual(one.rejected, (("b", "insufficient_funds"),))

    def test_duplicate_retry_never_double_spends(self):
        cmd = Intent("id", "owner", "alice", "bob", 2, 0)
        one = advance(self.initial, [cmd, cmd], self.grants)
        self.assertEqual(one.accepted, ("id",))
        stale = Intent("id", "owner", "alice", "bob", 2, 1)
        two = advance(one.world, [stale], self.grants)
        self.assertEqual(two.world.accounts, one.world.accounts)
        self.assertEqual(two.rejected[0][1], "duplicate_or_missing_id")

    def test_stale_tick_fails_closed(self):
        out = advance(self.initial, [Intent("id", "owner", "alice", "bob", 1, 9)], self.grants)
        self.assertEqual(out.rejected[0][1], "stale_tick")

    def test_replay_matches_fingerprint_and_hash_chain(self):
        batch = [Intent("req-1", "owner", "alice", "bob", 3, 0)]
        one = advance(self.initial, batch, self.grants).world
        self.assertEqual(one.fingerprint(), replay(self.initial, [batch], self.grants).fingerprint())
        second = advance(one, [Intent("req-2", "owner", "alice", "eve", 2, 1)], self.grants).world
        self.assertEqual(second.events[1].prev_hash, second.events[0].digest)

    def test_empty_tick_is_replayable(self):
        self.assertEqual(replay(self.initial, [[]], self.grants).tick, 1)


if __name__ == "__main__":
    unittest.main()
