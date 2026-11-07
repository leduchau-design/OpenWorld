"""W4 research-only persisted capability revocation, scoped to a trusted local host.

NOT an identity provider or unbypassable network authorization boundary.
The local SQLite file must be owned, backed up and protected by a trusted host.
"""
from __future__ import annotations

from pathlib import Path
from contextlib import closing
import sqlite3
import time
from urllib.parse import quote

from .trust_boundaries import CapabilityAuthority, TrustBoundaryError


class SQLiteRevocationStore:
    """Monotone, issuer/audience/nonce-scoped deny registry.

    Each call opens a new SQLite connection. There is deliberately no 'unrevoke'
    method. A missing/corrupt registry denies verification, but a hostile host
    can still replace the whole database and its keys: external custody is needed.
    """

    def __init__(self, path: str | Path):
        if not isinstance(path, (str, Path)) or str(path) in {"", ":memory:"}:
            raise ValueError("a real local SQLite file path is required")
        self.path = Path(path).resolve()
        # Do not silently use a directory or a nonexisting parent.
        if not self.path.parent.is_dir():
            raise ValueError("revocation database parent must already exist")
        with closing(sqlite3.connect(str(self.path), timeout=10)) as db:
            with db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA synchronous=FULL")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS capability_revocations ("
                    " issuer TEXT NOT NULL, audience TEXT NOT NULL,"
                    " nonce TEXT NOT NULL, revoked_at INTEGER NOT NULL,"
                    " PRIMARY KEY (issuer, audience, nonce))"
                )

    def _connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        mode = "ro" if read_only else "rw"
        # URI-mode with rw/ro refuses to silently re-create a deleted registry.
        uri = "file:" + quote(str(self.path), safe="/") + "?mode=" + mode
        try:
            return sqlite3.connect(uri, uri=True, timeout=10)
        except sqlite3.Error as exc:
            raise TrustBoundaryError("revocation registry unavailable") from exc

    @staticmethod
    def _validate(issuer: str, audience: str, nonce: str) -> None:
        if any(not isinstance(v, str) or not v or len(v) > 256
               for v in (issuer, audience, nonce)):
            raise ValueError("invalid revocation identity")

    def revoke(self, *, issuer: str, audience: str, nonce: str,
               revoked_at: int | None = None) -> None:
        self._validate(issuer, audience, nonce)
        stamp = int(time.time()) if revoked_at is None else revoked_at
        if type(stamp) is not int or stamp < 0:
            raise ValueError("invalid revocation timestamp")
        with closing(self._connect()) as db:
            with db:
                try:
                    db.execute("PRAGMA synchronous=FULL")
                    db.execute(
                        "INSERT OR IGNORE INTO capability_revocations "
                        "(issuer, audience, nonce, revoked_at) VALUES (?,?,?,?)",
                        (issuer, audience, nonce, stamp),
                    )
                except sqlite3.Error as exc:
                    raise TrustBoundaryError("revocation registry write failed") from exc

    def is_revoked(self, *, issuer: str, audience: str, nonce: str) -> bool:
        self._validate(issuer, audience, nonce)
        try:
            with closing(self._connect(read_only=True)) as db:
                row = db.execute(
                    "SELECT 1 FROM capability_revocations "
                    "WHERE issuer=? AND audience=? AND nonce=?",
                    (issuer, audience, nonce),
                ).fetchone()
        except sqlite3.Error as exc:
            raise TrustBoundaryError("revocation registry read failed") from exc
        return row is not None


class PersistedCapabilityAuthority(CapabilityAuthority):
    """Optional research adapter; host MUST expose only this verifier.

    Verification has a revocation read/check race with external actions. A host
    must serialize its grant-check/commit boundary for stronger guarantees.
    """

    def __init__(self, key: bytes, *, issuer: str, audience: str,
                 revocation_store: SQLiteRevocationStore):
        if not isinstance(revocation_store, SQLiteRevocationStore):
            raise TypeError("persisted revocation store is required")
        super().__init__(key, issuer=issuer, audience=audience)
        self.revocation_store = revocation_store

    def revoke(self, nonce: str) -> None:
        if not isinstance(nonce, str) or not nonce:
            raise ValueError("nonce required")
        self.revocation_store.revoke(issuer=self.issuer,
                                     audience=self.audience, nonce=nonce)
        super().revoke(nonce)

    def verify(self, token: str, *, authenticated_principal: str, owner: str,
               resource: str, action: str, now: int | None = None):
        grant = super().verify(
            token, authenticated_principal=authenticated_principal,
            owner=owner, resource=resource, action=action, now=now,
        )
        if self.revocation_store.is_revoked(
            issuer=grant.issuer, audience=grant.audience, nonce=grant.nonce,
        ):
            raise PermissionError("persistently revoked capability")
        return grant
