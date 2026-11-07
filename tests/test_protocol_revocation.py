"""W4 revocation reference tests: synthetic keys and no public identities."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.protocol_revocation import (
    PersistedCapabilityAuthority, SQLiteRevocationStore,
)
from openworld_superkernel.trust_boundaries import TrustBoundaryError

KEY = b"synthetic strong HMAC test key not for production"
START, END, NOW = 100, 200, 120


class PersistedRevocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "revoked.sqlite3"
        self.store = SQLiteRevocationStore(self.path)
        self.authority = self.make_authority()
        self.token = self.authority.issue(
            principal="principal-a", owner="owner-a", resource="agent-a",
            action="read_world", valid_from=START, expires_at=END,
            nonce="nonce-a",
        )

    def make_authority(self, issuer="local-issuer", audience="local-world"):
        return PersistedCapabilityAuthority(
            KEY, issuer=issuer, audience=audience,
            revocation_store=SQLiteRevocationStore(self.path),
        )

    def check(self, auth=None, token=None, **overrides):
        kwargs = dict(authenticated_principal="principal-a",
                      owner="owner-a", resource="agent-a",
                      action="read_world", now=NOW)
        kwargs.update(overrides)
        return (auth or self.authority).verify(token or self.token, **kwargs)

    def test_unrevoked_token_has_same_scope_checks(self):
        self.assertEqual(self.check().nonce, "nonce-a")
        with self.assertRaises(PermissionError):
            self.check(authenticated_principal="attacker")
        with self.assertRaises(PermissionError):
            self.check(owner="other")
        with self.assertRaises(PermissionError):
            self.check(action="write_agent")

    def test_revocation_survives_new_authority(self):
        self.authority.revoke("nonce-a")
        with self.assertRaises(PermissionError):
            self.check()
        with self.assertRaises(PermissionError):
            self.check(auth=self.make_authority())

    def test_revocation_visible_to_already_running_authority(self):
        independent = self.make_authority()
        self.assertEqual(self.check(auth=independent).nonce, "nonce-a")
        self.authority.revoke("nonce-a")
        with self.assertRaises(PermissionError):
            self.check(auth=independent)

    def test_revocation_survives_new_python_process(self):
        self.authority.revoke("nonce-a")
        child = """
import sys
from openworld_superkernel.protocol_revocation import (
  PersistedCapabilityAuthority, SQLiteRevocationStore
)
key=b'synthetic strong HMAC test key not for production'
authority=PersistedCapabilityAuthority(key,issuer='local-issuer',
  audience='local-world',revocation_store=SQLiteRevocationStore(sys.argv[1]))
try:
  authority.verify(sys.argv[2], authenticated_principal='principal-a',
    owner='owner-a',resource='agent-a',action='read_world',now=120)
except PermissionError:
  print('REVOKED')
  sys.exit(0)
sys.exit(99)
"""
        env = os.environ.copy()
        src = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (src, env.get("PYTHONPATH", ""))))
        process = subprocess.run(
            [sys.executable, "-c", child, str(self.path), self.token],
            env=env, text=True, capture_output=True, timeout=15, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.strip(), "REVOKED")

    def test_missing_registry_fails_closed(self):
        self.path.unlink()
        with self.assertRaises(TrustBoundaryError):
            self.check()

    def test_missing_table_fails_closed(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TABLE capability_revocations")
        with self.assertRaises(TrustBoundaryError):
            self.check()

    def test_revocation_idempotent_and_namespace_bound(self):
        self.authority.revoke("nonce-a")
        self.authority.revoke("nonce-a")
        with sqlite3.connect(self.path) as db:
            count = db.execute(
                "SELECT count(*) FROM capability_revocations "
                "WHERE issuer='local-issuer' AND audience='local-world' "
                "AND nonce='nonce-a'"
            ).fetchone()[0]
        self.assertEqual(count, 1)
        # A different issuer sharing the registry has an independent nonce scope.
        other = self.make_authority(issuer="different-issuer")
        token = other.issue(principal="principal-a", owner="owner-a",
                            resource="agent-a", action="read_world",
                            valid_from=START, expires_at=END, nonce="nonce-a")
        self.assertEqual(self.check(auth=other, token=token).nonce, "nonce-a")

    def test_expiry_is_still_enforced(self):
        with self.assertRaises(PermissionError):
            self.check(now=END)
        with self.assertRaises(PermissionError):
            self.check(now=START - 1)

    def test_invalid_store_and_timestamp(self):
        with self.assertRaises(ValueError):
            SQLiteRevocationStore(":memory:")
        with self.assertRaises(ValueError):
            self.store.revoke(issuer="local-issuer", audience="local-world",
                              nonce="nonce-b", revoked_at=-1)


if __name__ == "__main__":
    unittest.main()
