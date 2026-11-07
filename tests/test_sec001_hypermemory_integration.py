"""Integration checks: SEC-001 against the real HM-P1e SQLite store.

The capability gateway remains research-only; an external host must authenticate
principal identities and prevent bypass access to the raw store.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e, Observation
from openworld_superkernel.memory_contracts import MemoryEvent, Provenance
from openworld_superkernel.trust_boundaries import (
    CapabilityAuthority, ScopedMemoryReader, TrustBoundaryError,
    capture_anchor, ledger_snapshot, online_backup, verify_anchor,
)

DEMO_KEY = b"test-only synthetic external security key never use in production"


class TestRealMemoryTrustBoundaries(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.root = Path(self.workspace.name)
        self.memory = HyperMemoryP1e(self.root / "memory.db")
        self.now = int(time.time())
        self.authority = CapabilityAuthority(DEMO_KEY, issuer="research",
                                              audience="openworld")
        self.identity = "test-principal"
        self.gateway = ScopedMemoryReader(
            self.memory, self.authority,
            authenticated_principal=lambda: self.identity,
        )

    def tearDown(self):
        self.memory.close()
        self.workspace.cleanup()

    def add(self, agent: str, *, owner: str = "owner-one",
            event_type: str = "consent") -> tuple[str, bytes]:
        event_id = f"{agent}:event-1"
        payload = f"synthetic evidence {agent}".encode("ascii")
        observation = Observation(
            event=MemoryEvent(event_id=event_id, owner_id=owner,
                              event_type=event_type,
                              provenance=Provenance.OBSERVED_RECORDED,
                              payload=payload, protected=True),
            agent_id=agent, sequence_number=1, outcome=1,
        )
        applied = self.memory.apply_batch([observation],
                                           requester_owner_id=owner)
        self.assertEqual(applied, 1)
        return event_id, payload

    def grant(self, *, action: str, resource: str, owner="owner-one"):
        return self.authority.issue(
            principal="test-principal", owner=owner, resource=resource,
            action=action, valid_from=self.now - 1, expires_at=self.now + 60,
        )

    def test_real_store_has_scope_enforced_by_gateway(self):
        event_id, payload = self.add("alpha")
        state_grant = self.grant(action="read_state", resource="alpha")
        event_grant = self.grant(action="read_event", resource=event_id)
        self.assertEqual(self.gateway.read_state(
            state_grant, owner="owner-one", agent="alpha")["n"], 1)
        self.assertEqual(self.gateway.read_event(
            event_grant, owner="owner-one", event_id=event_id), payload)
        with self.assertRaises(PermissionError):
            self.gateway.read_event(event_grant, owner="owner-two",
                                    event_id=event_id)
        with self.assertRaises(PermissionError):
            self.gateway.read_state(state_grant, owner="owner-one",
                                    agent="beta")

    def test_external_identity_mismatch_fails_closed(self):
        event_id, _ = self.add("alpha")
        token = self.grant(action="read_event", resource=event_id)
        self.identity = "impersonated-principal"
        with self.assertRaises(PermissionError):
            self.gateway.read_event(token, owner="owner-one", event_id=event_id)

    def test_five_agent_backup_and_anchor_recovery(self):
        agents = [f"agent-{i}" for i in range(5)]
        anchors = {}
        for agent in agents:
            self.add(agent)
            anchors[agent] = capture_anchor(
                self.memory.db, owner="owner-one", agent=agent,
                external_signing_key=DEMO_KEY,
            )
        backup = self.root / "online-backup.db"
        online_backup(self.memory.db, backup)
        with sqlite3.connect(backup) as restored:
            for agent in agents:
                self.assertTrue(verify_anchor(
                    restored, signed_anchor=anchors[agent],
                    external_verification_key=DEMO_KEY,
                    owner="owner-one", agent=agent,
                ))
                self.assertEqual(ledger_snapshot(
                    restored, owner="owner-one", agent=agent)["count"], 1)

    def test_rewritten_payload_and_hash_do_not_pass_external_anchor(self):
        event_id, _ = self.add("alpha")
        signed = capture_anchor(
            self.memory.db, owner="owner-one", agent="alpha",
            external_signing_key=DEMO_KEY)
        tampered = b"modified synthetic evidence"
        self.memory.db.execute(
            "UPDATE exact_events SET payload=?, payload_hash=? WHERE event_id=?",
            (tampered, hashlib.sha256(tampered).hexdigest(), event_id),
        )
        with self.assertRaises(TrustBoundaryError):
            verify_anchor(
                self.memory.db, signed_anchor=signed,
                external_verification_key=DEMO_KEY,
                owner="owner-one", agent="alpha",
            )

    def test_isolated_other_owner_exact_events(self):
        own_id, own_payload = self.add("alpha", owner="owner-one")
        other_id, other_payload = self.add("beta", owner="owner-two")
        first = self.grant(action="read_event", resource=own_id)
        self.assertEqual(
            self.gateway.read_event(first, owner="owner-one", event_id=own_id),
            own_payload)
        with self.assertRaises(PermissionError):
            self.gateway.read_event(first, owner="owner-two", event_id=other_id)
        self.assertNotEqual(own_payload, other_payload)


if __name__ == "__main__":
    unittest.main()
