"""Adversarial, CPU-only tests for SEC-002 local authorization reference."""
import concurrent.futures
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openworld_superkernel.durable_identity import (
    LocalSessionVerifier, DurableCapabilityAuthority, AuthenticatedMemoryReader,
    AuthenticationError, AuthorizationError,
)
try:
    from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e, Observation
    from openworld_superkernel.memory_contracts import MemoryEvent, Provenance
    HAS_HM_P1E = True
except ModuleNotFoundError:
    HAS_HM_P1E = False


IDP_KEY = b"local-test-idp-not-for-production-000000000000000"
ISSUER_KEY_1 = b"local-test-cap-issuer-0000000000000000000000000"
ISSUER_KEY_2 = b"local-test-rotated-key-0000000000000000000"


class Clock:
    def __init__(self):
        self.value = 1000

    def __call__(self):
        return self.value


class IdentityGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "authority.sqlite"
        self.clock = Clock()
        self.idp = LocalSessionVerifier(IDP_KEY, issuer="idp-test", audience="ow-service", clock=self.clock)
        self.db = self.authority()
        self.alice = self.idp.issue("alice")
        self.bob = self.idp.issue("bob")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def authority(self, keys=None, active="kid-1"):
        return DurableCapabilityAuthority(self.path, issuer="ow-issuer", audience="ow-service",
                session_verifier=self.idp, keys=keys or {"kid-1": ISSUER_KEY_1},
                active_kid=active, clock=self.clock)

    def grant(self, subject="bob", **changes):
        values = dict(owner="alice", subject=subject, agent="agent-a", resource="agent-a",
                      action="read_state", purpose="simulation", lifetime=200, max_uses=1)
        values.update(changes)
        return self.db.issue(self.alice, **values)

    def permit(self, token, caller=None, **changes):
        values = dict(owner="alice", agent="agent-a", resource="agent-a",
                      action="read_state", purpose="simulation")
        values.update(changes)
        return self.db.authorize(caller or self.bob, token, **values)

    def test_authentication_is_not_self_assertion(self):
        token = self.grant()
        with self.assertRaises(AuthenticationError):
            self.permit(token, caller="bob")

    def test_authenticated_subject_can_use_scoped_grant(self):
        self.assertEqual(self.permit(self.grant()), "bob")
        self.assertEqual(len(self.db.audit_events()), 2)

    def test_not_owner_cannot_issue_others_grants(self):
        with self.assertRaises(AuthorizationError):
            self.db.issue(self.bob, owner="alice", subject="bob", agent="a",
                          resource="a", action="read_state", purpose="simulation")

    def test_replay_exhausts_one_use(self):
        t = self.grant()
        self.permit(t)
        with self.assertRaises(AuthorizationError):
            self.permit(t)

    def test_durable_replay_after_restart(self):
        t = self.grant()
        self.permit(t)
        self.db.close()
        self.db = self.authority()
        with self.assertRaises(AuthorizationError):
            self.permit(t)

    def test_revoked_grant_stays_revoked_after_restart(self):
        t = self.grant()
        self.db.revoke(self.alice, grant_token=t)
        self.db.close()
        self.db = self.authority()
        with self.assertRaises(AuthorizationError):
            self.permit(t)

    def test_caller_cannot_revoke_other_owner(self):
        t = self.grant()
        with self.assertRaises(AuthorizationError):
            self.db.revoke(self.bob, grant_token=t)
        self.permit(t)

    def test_wrong_principal_denied(self):
        t = self.grant(subject="alice")
        with self.assertRaises(AuthorizationError):
            self.permit(t)

    def test_different_scope_and_purpose_fail(self):
        t = self.grant()
        for field, value in (("agent", "agent-b"), ("owner", "mallory"),
                             ("purpose", "billing"), ("resource", "event-a"),
                             ("action", "write_agent")):
            with self.subTest(field=field), self.assertRaises(AuthorizationError):
                self.permit(t, **{field: value})
        self.permit(t)

    def test_expiry_and_not_yet_valid(self):
        t = self.grant()
        self.clock.value = 999
        with self.assertRaises(AuthorizationError):
            self.permit(t, caller=self.idp.issue("bob"))
        self.clock.value = 1200
        with self.assertRaises(AuthorizationError):
            self.permit(t, caller=self.idp.issue("bob"))

    def test_expired_session_denied_even_with_live_grant(self):
        t = self.grant(lifetime=600)
        self.clock.value = 1120
        with self.assertRaises(AuthenticationError):
            self.permit(t)

    def test_invalid_idp_audience_denied(self):
        other = LocalSessionVerifier(IDP_KEY, issuer="idp-test", audience="other", clock=self.clock)
        with self.assertRaises(AuthenticationError):
            self.permit(self.grant(), caller=other.issue("bob"))

    def test_malformed_and_duplicate_claim_denied(self):
        t = self.grant()
        obj = json.loads(t)
        obj["body"]["purpose"] = "payments"
        with self.assertRaises(AuthorizationError):
            self.permit(json.dumps(obj))
        with self.assertRaises(AuthorizationError):
            self.permit('{"body":{},"body":{},"signature":"' + 'a'*64 + '"}')

    def test_not_in_registry_even_when_signed(self):
        t = self.grant()
        body = json.loads(t)["body"]
        body["jti"] = "stolen-but-valid-identity"
        from openworld_superkernel.durable_identity import _sign
        t2 = _sign(body, ISSUER_KEY_1)
        with self.assertRaises(AuthorizationError):
            self.permit(t2)

    def test_rotation_accepts_retired_key_until_revoke(self):
        old = self.grant()
        self.db.rotate(new_kid="kid-2", new_key=ISSUER_KEY_2)
        new = self.grant()
        self.permit(old)
        self.permit(new)
        self.assertEqual(len(self.db.audit_events()), 5)

    def test_revoked_old_key_fails_across_restarts(self):
        t = self.grant()
        self.db.rotate(new_kid="kid-2", new_key=ISSUER_KEY_2)
        self.db.revoke_key("kid-1")
        self.db.close()
        self.db = self.authority(keys={"kid-2": ISSUER_KEY_2}, active="kid-2")
        with self.assertRaises(AuthorizationError):
            self.permit(t)

    def test_key_id_cannot_be_reused(self):
        self.db.rotate(new_kid="kid-2", new_key=ISSUER_KEY_2)
        self.db.revoke_key("kid-1")
        with self.assertRaises(ValueError):
            self.db.rotate(new_kid="kid-1", new_key=ISSUER_KEY_1)

    def test_key_loss_fails_closed_at_restart(self):
        self.db.rotate(new_kid="kid-2", new_key=ISSUER_KEY_2)
        self.db.close()
        with self.assertRaises(AuthenticationError):
            self.authority(keys={"kid-1": ISSUER_KEY_1}, active="kid-2")
        self.db = self.authority(keys={"kid-2": ISSUER_KEY_2}, active="kid-2")

    def test_config_mismatch_restart_denied(self):
        self.db.close()
        with self.assertRaises(AuthenticationError):
            DurableCapabilityAuthority(self.path, issuer="wrong", audience="ow-service",
                session_verifier=self.idp, keys={"kid-1": ISSUER_KEY_1},
                active_kid="kid-1", clock=self.clock)
        self.db = self.authority()

    def test_atomic_max_use_under_concurrency(self):
        t = self.grant(max_uses=1)
        def attempt(_):
            with self.authority() as instance:
                try:
                    return instance.authorize(self.bob, t, owner="alice", agent="agent-a",
                         resource="agent-a", action="read_state", purpose="simulation")
                except AuthorizationError:
                    return "denied"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), ["bob", "denied"])
        self.assertEqual(self.db.db.execute("SELECT used FROM grants").fetchone()[0], 1)

    def test_consumption_rolls_back_on_audit_failure(self):
        t = self.grant()
        self.db.db.execute("CREATE TRIGGER audit_failure BEFORE INSERT ON audit_log "
                           "WHEN NEW.event='consume' BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.permit(t)
        self.assertEqual(self.db.db.execute("SELECT used FROM grants").fetchone(), (0,))
        self.db.db.execute("DROP TRIGGER audit_failure")
        self.permit(t)

    def test_input_limits(self):
        for data in ({"lifetime": True}, {"lifetime": 4000}, {"max_uses": 0},
                     {"action": "admin"}, {"subject": ""}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.grant(**data)

    @unittest.skipUnless(HAS_HM_P1E, "requires integrated HM-P1e repository")
    def test_guarded_memory_read(self):
        memory = HyperMemoryP1e(Path(self.tmp.name) / "memory.sqlite")
        try:
            e = MemoryEvent("e-1", "alice", "consent", Provenance.OBSERVED_RECORDED,
                            b"exact evidence")
            memory.apply_batch([Observation(e, "agent-a", 1, 1)],
                               requester_owner_id="alice")
            gate = AuthenticatedMemoryReader(self.db, memory)
            state_grant = self.grant(action="read_state")
            observed = gate.read_state(self.bob, state_grant, owner="alice",
                                       agent="agent-a", purpose="simulation")
            self.assertEqual(observed["n"], 1)
            with self.assertRaises(AuthorizationError):
                gate.read_state(self.bob, state_grant, owner="alice",
                                agent="agent-a", purpose="simulation")
            event_grant = self.grant(action="read_event", resource="e-1")
            self.assertEqual(gate.read_event(self.bob, event_grant, owner="alice",
                                             agent="agent-a", event_id="e-1",
                                             purpose="simulation"), b"exact evidence")
        finally:
            memory.close()

    @unittest.skipUnless(HAS_HM_P1E, "requires integrated HM-P1e repository")
    def test_same_owner_different_agent_event_is_denied(self):
        memory = HyperMemoryP1e(Path(self.tmp.name) / "memory.sqlite")
        try:
            event = MemoryEvent("event-b", "alice", "consent",
                                Provenance.OBSERVED_RECORDED, b"agent-b secret")
            memory.apply_batch([Observation(event, "agent-b", 1, 1)],
                               requester_owner_id="alice")
            gateway = AuthenticatedMemoryReader(self.db, memory)
            scoped = self.grant(action="read_event", resource="event-b")
            with self.assertRaises(AuthorizationError):
                gateway.read_event(self.bob, scoped, owner="alice", agent="agent-a",
                                   event_id="event-b", purpose="simulation")
        finally:
            memory.close()

    @unittest.skipUnless(HAS_HM_P1E, "requires integrated HM-P1e repository")
    def test_unauthorized_memory_read_does_not_consume(self):
        memory = HyperMemoryP1e(Path(self.tmp.name) / "memory.sqlite")
        try:
            gate = AuthenticatedMemoryReader(self.db, memory)
            t = self.grant()
            with self.assertRaises(AuthorizationError):
                gate.read_state(self.bob, t, owner="alice", agent="wrong-agent",
                                purpose="simulation")
            self.assertEqual(self.db.db.execute("SELECT used FROM grants").fetchone(), (0,))
        finally:
            memory.close()


if __name__ == "__main__":
    unittest.main()