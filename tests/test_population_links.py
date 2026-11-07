"""W3 local population routing: positive, adversarial and replay controls."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.population_links import (
    Exchange, Population, PopulationLink, PopulationRouter,
)
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_guard import GuardedWorldGateway
from openworld_superkernel.world_fixture import (
    Action, Agent, Weather, create_world, verify_replay,
)

TEST_KEY = b"population-link-synthetic-key-for-testing-only-do-not-deploy"


class LocalPopulationLinksTests(unittest.TestCase):
    def setUp(self):
        self.authority = CapabilityAuthority(TEST_KEY, issuer="local-test",
                                             audience="world")
        self.principal = "test-host"
        self.gateway = GuardedWorldGateway(
            self.authority, authenticated_principal=lambda: self.principal)
        self.genesis = create_world((
            Agent("a", "owner-1", "north", 7),
            Agent("b", "owner-1", "north", 0),
            Agent("c", "owner-1", "south", 3),
            Agent("d", "owner-1", "south", 1),
        ), (("a", "b"), ("b", "c"), ("c", "d")), seed=17)
        self.groups = (
            Population("builders", ("a", "b")),
            Population("traders", ("c", "d")),
        )
        self.links = (
            PopulationLink("builders", "traders", ("signal", "transfer"),
                           max_transfer=4, max_actions_per_tick=2),
            PopulationLink("traders", "builders", ("signal",),
                           max_actions_per_tick=1),
        )
        self.router = PopulationRouter(self.gateway, self.groups, self.links)
        now = int(time.time())
        self.start, self.end = now - 30, now + 90

    def grant(self, agent, *, principal="test-host", owner="owner-1",
              action="write_agent"):
        return self.authority.issue(
            principal=principal, owner=owner, resource=agent, action=action,
            valid_from=self.start, expires_at=self.end,
            nonce=f"grant-{agent}-{principal}-{action}")

    def exchange(self, *, request_id="req-1", actor="b", target="c",
                 source="builders", dest="traders", kind="transfer", amount=2,
                 actor_capability=None, target_capability=None, tick=0,
                 owner="owner-1"):
        action = Action(request_id, tick, owner, actor, target, kind, amount)
        return Exchange(
            source, dest, action,
            self.grant(actor) if actor_capability is None else actor_capability,
            self.grant(target) if target_capability is None else target_capability,
        )

    def test_two_population_transfer_and_exact_replay(self):
        out = self.router.advance(self.genesis, exchanges=(self.exchange(),))
        self.assertEqual(out.state.accepted, ())
        self.assertEqual(out.state.rejected, (("req-1", "insufficient_resources"),))
        self.assertEqual(out.state.world.balances, self.genesis.balances)
        self.assertTrue(verify_replay(self.genesis, out.state.world))

    def test_signal_is_recorded_as_simulated(self):
        out = self.router.advance(self.genesis, exchanges=(
            self.exchange(kind="signal", amount=0),
        ))
        self.assertEqual(len(out.events_added), 1)
        self.assertEqual(out.events_added[0].provenance, "SIMULATED")
        self.assertEqual(out.events_added[0].kind, "signal")
        self.assertTrue(verify_replay(self.genesis, out.state.world))

    def test_no_resources_rejects_without_creating_event(self):
        out = self.router.advance(self.genesis, exchanges=(self.exchange(),))
        self.assertEqual(out.state.accepted, ())
        self.assertEqual(out.state.rejected, (("req-1", "insufficient_resources"),))
        self.assertEqual(out.events_added, ())
        self.assertEqual(out.state.world.balances, self.genesis.balances)
        self.assertTrue(verify_replay(self.genesis, out.state.world))

    def test_transfer_after_valid_resource_source(self):
        # Action-dependent balances are authoritative W3 state, not bridge state.
        g = create_world((
            Agent("a", "owner-1", "north", 7),
            Agent("b", "owner-1", "north", 4),
            Agent("c", "owner-1", "south", 3),
            Agent("d", "owner-1", "south", 1),
        ), (("a", "b"), ("b", "c"), ("c", "d")), seed=17)
        out = self.router.advance(g, exchanges=(self.exchange(),))
        self.assertEqual(out.state.accepted, ("req-1",))
        self.assertEqual(dict(out.state.world.balances)["b"], 2)
        self.assertEqual(dict(out.state.world.balances)["c"], 5)
        self.assertTrue(verify_replay(g, out.state.world))

    def test_cross_owner_transfer_cannot_bypass_guard(self):
        world = create_world((
            Agent("a", "owner-1", "north", 7),
            Agent("b", "owner-1", "north", 2),
            Agent("c", "owner-2", "south", 3),
            Agent("d", "owner-2", "south", 1),
        ), (("a", "b"), ("b", "c"), ("c", "d")), seed=17)
        with self.assertRaisesRegex(PermissionError, "cross-owner"):
            self.router.advance(world, exchanges=(self.exchange(),))
        self.assertEqual(world.tick, 0)
        self.assertFalse(world.events)

    def test_target_grant_is_required_and_scoped(self):
        with self.assertRaises(Exception):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(kind="signal", amount=0, target_capability="invalid"),
            ))
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(kind="signal", amount=0,
                              target_capability=self.grant("a")),
            ))
        self.assertEqual(self.genesis.tick, 0)

    def test_actor_grant_is_required_too(self):
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(kind="signal", amount=0,
                              actor_capability=self.grant("c")),
            ))

    def test_revoke_target_grant_fails_before_w3(self):
        token = self.grant("c")
        self.authority.revoke(json.loads(token)["body"]["nonce"])
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(kind="signal", amount=0,
                              target_capability=token),
            ))
        self.assertEqual(len(self.genesis.events), 0)

    def test_no_link_or_direction_denied(self):
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(actor="c", target="b", source="traders",
                              dest="builders", kind="transfer", amount=1),
            ))

    def test_not_neighbors_denied(self):
        with self.assertRaisesRegex(PermissionError, "adjacency"):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(actor="a", target="d"),
            ))

    def test_invalid_amount_and_contract_quota_denied(self):
        with self.assertRaises(ValueError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(amount=5),
            ))
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(request_id="a", kind="signal", amount=0),
                self.exchange(request_id="b", kind="signal", amount=0),
                self.exchange(request_id="c", kind="signal", amount=0),
            ))
        self.assertEqual(self.genesis.tick, 0)

    def test_all_or_none_precheck_validation(self):
        correct = self.exchange(request_id="first", kind="signal", amount=0)
        forged = self.exchange(request_id="second", kind="signal", amount=0,
                               target_capability=self.grant("a"))
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(correct, forged))
        self.assertFalse(self.genesis.events)

    def test_duplicate_request_ids_rejected_before_tick(self):
        with self.assertRaisesRegex(ValueError, "duplicate request"):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(request_id="same", kind="signal", amount=0),
                self.exchange(request_id="same", kind="signal", amount=0),
            ))

    def test_wrong_tick_or_membership_denied(self):
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(kind="signal", amount=0, tick=7),
            ))
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(source="traders", kind="signal", amount=0),
            ))

    def test_missing_roster_or_duplicate_membership(self):
        with self.assertRaises(ValueError):
            PopulationRouter(self.gateway,
                             (Population("a", ("a", "b")),
                              Population("b", ("b", "c"))), self.links)
        incomplete = PopulationRouter(
            self.gateway, (Population("builders", ("a", "b")),
                           Population("traders", ("c",))), self.links)
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            incomplete.advance(self.genesis, exchanges=())

    def test_external_tick_with_no_actions_is_replayable(self):
        out = self.router.advance(self.genesis, exchanges=(),
                                  external=(Weather("north", "rain"),))
        self.assertEqual(out.state.world.tick, 1)
        self.assertEqual(out.events_added[0].kind, "weather.rain")
        self.assertTrue(verify_replay(self.genesis, out.state.world))

    def test_untrusted_principal_missing_denied(self):
        self.principal = ""
        with self.assertRaises(PermissionError):
            self.router.advance(self.genesis, exchanges=(
                self.exchange(kind="signal", amount=0),
            ))


    def test_three_population_30_agent_demo_is_replayable(self):
        import subprocess
        script = Path(__file__).resolve().parents[1] / "examples" / "populations" / "local_three_groups.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            text=True, capture_output=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["population_count"], 3)
        self.assertEqual(report["registered_agents"], 30)
        self.assertEqual(report["owners"], 1)
        self.assertEqual(report["ticks"], 2)
        self.assertEqual(report["replay"], "PASS")
        self.assertEqual(report["total_resources"], 150)
        self.assertEqual(len(report["accepted"]), 5)
        self.assertEqual(len(report["event_kinds"]), 5)
        self.assertEqual(report["rejected"], [])
        self.assertEqual(report["selected_balances"], {
            "a09": 3, "a10": 7, "a19": 4, "a20": 6,
        })


if __name__ == "__main__":
    unittest.main()
