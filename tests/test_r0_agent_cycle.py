"""Bounded R0 positive/negative tests; do not equate to independent Gate #11."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e
from openworld_superkernel.r0_cycle import run_cycle
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_fixture import Agent, create_world, verify_replay
from openworld_superkernel.world_guard import GuardedWorldGateway


class R0CycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.memory = HyperMemoryP1e(Path(temp.name) / "hm.sqlite3")
        self.addCleanup(self.memory.close)
        self.owner, self.principal = "one-owner", "trusted-host"
        self.genesis = create_world((
            Agent("a", self.owner, "r", 3),
            Agent("b", self.owner, "r", 3),
        ), (("a", "b"),), seed=42)
        self.auth = CapabilityAuthority(
            b"R0_UNIT_TEST_EPHEMERAL_KEY_32_BYTES_LONG", issuer="test", audience="world",
        )
        self.gateway = GuardedWorldGateway(
            self.auth, authenticated_principal=lambda: self.principal,
        )
        now = int(time.time())
        self.read = self.auth.issue(
            principal=self.principal, owner=self.owner, resource="a",
            action="read_world", valid_from=now - 10, expires_at=now + 200,
        )
        self.write = self.auth.issue(
            principal=self.principal, owner=self.owner, resource="a",
            action="write_agent", valid_from=now - 10, expires_at=now + 200,
            nonce="r0-write-test-nonce",
        )

    def cycle(self, world=None, **updates):
        args = dict(
            genesis=self.genesis, world=self.genesis if world is None else world,
            memory=self.memory, gateway=self.gateway, owner_id=self.owner,
            agent_id="a", target_id="b",
            read_capability=self.read, write_capability=self.write,
            simulated_outcome=0,
        )
        args.update(updates)
        return run_cycle(**args)

    def state(self):
        return self.memory.get_state(
            owner_id=self.owner, agent_id="a", requester_owner_id=self.owner,
        )

    def test_full_cycle_changes_policy_and_preserves_simulated_provenance(self):
        first = self.cycle()
        self.assertEqual(first.action_kind, "transfer")
        self.assertEqual(first.prediction, 0.5)
        self.assertEqual(dict(first.world.balances), {"a": 2, "b": 4})
        self.assertTrue(verify_replay(self.genesis, first.world))
        stored = self.memory.exact_event(
            first.memory_event_id, requester_owner_id=self.owner,
        )
        self.assertEqual(json.loads(stored)["provenance"], "SIMULATED")
        self.assertEqual(self.state()["seq"], 1)
        second = self.cycle(world=first.world, simulated_outcome=1)
        self.assertEqual(second.action_kind, "signal")
        self.assertLess(second.prediction, 0.5)
        self.assertEqual(dict(second.world.balances), {"a": 2, "b": 4})
        self.assertEqual(self.state()["seq"], 2)
        self.assertEqual(len(second.world.journal), 2)
        self.assertTrue(verify_replay(self.genesis, second.world))

    def test_hold_never_fabricates_reward_or_memory_event(self):
        result = self.cycle(strategy="hold", write_capability=None,
                            simulated_outcome=None)
        self.assertEqual(result.action_kind, "hold")
        self.assertIsNone(result.memory_event_id)
        self.assertEqual(self.state()["n"], 0)
        self.assertEqual(result.world.tick, 1)
        self.assertEqual(result.world.balances, self.genesis.balances)

    def test_hold_with_outcome_denied(self):
        with self.assertRaises(ValueError):
            self.cycle(strategy="hold", simulated_outcome=1)
        self.assertEqual(self.state()["n"], 0)

    def test_invalid_feedback_denied_pre_action(self):
        for outcome in (True, -1, 2, None):
            with self.subTest(outcome=outcome):
                with self.assertRaises(ValueError):
                    self.cycle(simulated_outcome=outcome)
        self.assertEqual(self.state()["n"], 0)

    def test_missing_or_wrong_read_capability_denied(self):
        for cap in ("", self.write):
            with self.subTest(cap=bool(cap)):
                with self.assertRaises((ValueError, PermissionError)):
                    self.cycle(read_capability=cap)
        self.assertEqual(self.state()["n"], 0)

    def test_revoked_write_capability_denied_before_memory_write(self):
        self.auth.revoke("r0-write-test-nonce")
        with self.assertRaises(PermissionError):
            self.cycle()
        self.assertEqual(self.state()["n"], 0)

    def test_wrong_owner_target_denied(self):
        other_world = create_world((
            Agent("a", self.owner, "r", 3),
            Agent("b", "another-owner", "r", 3),
        ), (("a", "b"),), seed=42)
        with self.assertRaises(PermissionError):
            self.cycle(world=other_world, genesis=other_world)
        self.assertEqual(self.state()["n"], 0)

    def test_world_rejection_does_not_update_memory(self):
        world = create_world((
            Agent("a", self.owner, "r", 0),
            Agent("b", self.owner, "r", 5),
        ), (("a", "b"),), seed=42)
        with self.assertRaises(ValueError):
            self.cycle(world=world, genesis=world, strategy="fixed_transfer")
        self.assertEqual(self.state()["n"], 0)

    def test_world_replay_tampering_rejected(self):
        tampered = replace(self.genesis, balances=(("a", 99), ("b", 3)))
        with self.assertRaises(ValueError):
            self.cycle(world=tampered)
        self.assertEqual(self.state()["n"], 0)

    def test_non_neighbor_denied(self):
        with self.assertRaises(ValueError):
            self.cycle(target_id="unknown")
        self.assertEqual(self.state()["n"], 0)

    def test_single_command_demo_outputs_verifiable_simulated_trace(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(root / "examples" / "r0_agent_cycle.py")],
            cwd=root, capture_output=True, text=True, check=True, timeout=30,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(report["world_replay"], "PASS")
        self.assertEqual(report["owners"], 1)
        self.assertEqual(report["agents"], 2)
        self.assertTrue(all(item["prediction_provenance"] == "INFERRED"
                            for item in report["cycles"]))
        self.assertTrue(all(item["world_observation_provenance"] == "SIMULATED"
                            for item in report["cycles"]))
        self.assertEqual([item["action"] for item in report["cycles"]],
                         ["transfer", "signal", "transfer"])
        self.assertTrue(all(item["replay"] == "PASS" for item in report["cycles"]))
        self.assertIn("NOT atomic", report["limits"])

    def test_wrong_actor_claim_denied(self):
        with self.assertRaises(PermissionError):
            self.cycle(owner_id="another-owner")
        self.assertEqual(self.state()["n"], 0)


if __name__ == "__main__":
    unittest.main()
