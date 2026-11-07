"""Security known-negative controls: local SQLite restoration is not revocation proof.

These are deliberate EXPECTED FAILURES, not successful production security tests.
Do not remove until independently witnessed rollback prevention is implemented.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from openworld_superkernel.durable_identity import (
    AuthorizationError,
    DurableCapabilityAuthority,
    LocalSessionVerifier,
)


class Sec002StorageRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "authority.sqlite"
        self.backup_path = self.root / "prior-to-revocation.sqlite"
        self.clock = lambda: 1_000
        self.sessions = LocalSessionVerifier(
            b"synthetic-idp-key-only-for-negative-tests-0000000",
            issuer="test-idp",
            audience="test-service",
            clock=self.clock,
        )
        self.keys = {"kid-1": b"synthetic-issuer-key-only-for-negative-tests-000"}
        self.authority = self.new_authority()
        self.owner_session = self.sessions.issue("owner-a")
        self.caller_session = self.sessions.issue("caller-b")

    def tearDown(self) -> None:
        self.authority.close()
        self.temp.cleanup()

    def new_authority(self) -> DurableCapabilityAuthority:
        return DurableCapabilityAuthority(
            self.path,
            issuer="test-authority",
            audience="test-service",
            session_verifier=self.sessions,
            keys=self.keys,
            active_kid="kid-1",
            clock=self.clock,
        )

    def issue(self) -> str:
        return self.authority.issue(
            self.owner_session,
            owner="owner-a", subject="caller-b",
            agent="agent-a", resource="agent-a",
            action="read_state", purpose="research",
            lifetime=250, max_uses=1,
        )

    def authorize(self, token: str) -> str:
        return self.authority.authorize(
            self.caller_session, token,
            owner="owner-a", agent="agent-a",
            resource="agent-a", action="read_state",
            purpose="research",
        )

    def test_normal_restart_preserves_revocation(self) -> None:
        token = self.issue()
        self.authority.revoke(self.owner_session, grant_token=token)
        self.authority.close()
        self.authority = self.new_authority()
        with self.assertRaises(AuthorizationError):
            self.authorize(token)

    @unittest.expectedFailure
    def test_known_negative_restore_before_revocation_must_still_deny(self) -> None:
        """Known gap: an earlier database snapshot resurrects a valid capability."""
        token = self.issue()
        with sqlite3.connect(str(self.backup_path)) as backup:
            self.authority.db.backup(backup)
        self.authority.revoke(self.owner_session, grant_token=token)
        with self.assertRaises(AuthorizationError):
            self.authorize(token)
        self.authority.close()
        # This represents a genuine old-but-valid backup being restored.
        # SQLite closes/checkpoints before file replacement.
        shutil.copyfile(self.backup_path, self.path)
        self.authority = self.new_authority()
        # This SHOULD deny, but the old registry lacks a protected monotonic
        # revocation witness, so authorization currently succeeds.
        with self.assertRaises(AuthorizationError):
            self.authorize(token)

    @unittest.expectedFailure
    def test_known_negative_grant_consumption_and_effect_are_not_atomic(self) -> None:
        """Known gap: grant debit commits before a downstream action fails."""
        token = self.issue()
        self.assertEqual(self.authorize(token), "caller-b")
        # A separate world/network operation failed after grant-use commit.
        with self.assertRaises(RuntimeError):
            raise RuntimeError("simulated world operation failed")
        # An all-or-none operation would permit safe retry or offer a durable
        # reconciliation receipt. Neither exists at this integration boundary.
        self.assertEqual(self.authorize(token), "caller-b")


if __name__ == "__main__":
    unittest.main()
