"""SEC-003 research fence against stale authority database snapshots.

IMPORTANT: InMemoryWitness is an *in-process test double*, NOT a secure external
witness. Real deployments require an independently protected monotonic service,
authenticated transport and a reviewed in-doubt recovery protocol.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar


class WitnessUnavailable(PermissionError):
    """Trusted witness is absent, pending or inconsistent: deny authorization."""


@dataclass(frozen=True)
class WitnessHead:
    epoch: int
    digest: str
    pending: str | None


class MonotonicWitness(Protocol):
    """Contract to be provided by a genuinely independent trusted service."""

    def head(self) -> WitnessHead: ...
    def provision_empty_authority(self, digest: str) -> None: ...
    def begin(self, *, expected: WitnessHead, operation_id: str) -> None: ...
    def finalize(self, *, operation_id: str, digest: str) -> None: ...


class InMemoryWitness:
    """Isolated testing stand-in. Loss of this object means loss of authority.

    Persist it independently in tests across DB restore; it is not crash-safe,
    secure from a process adversary, globally monotonic or distributed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._head: WitnessHead | None = None
        self.available = True

    def _require(self) -> WitnessHead:
        if not self.available or self._head is None:
            raise WitnessUnavailable('trusted witness unavailable')
        return self._head

    def head(self) -> WitnessHead:
        with self._lock:
            return self._require()

    def provision_empty_authority(self, digest: str) -> None:
        with self._lock:
            if not self.available or self._head is not None:
                raise WitnessUnavailable('genesis witness cannot be replaced')
            _digest(digest)
            self._head = WitnessHead(0, digest, None)

    def begin(self, *, expected: WitnessHead, operation_id: str) -> None:
        if not operation_id or len(operation_id) > 128:
            raise ValueError('invalid operation ID')
        with self._lock:
            head = self._require()
            if head != expected or head.pending is not None:
                raise WitnessUnavailable('stale or pending witness')
            # Fencing begins *before* the database mutation. If anything fails,
            # remain pending/fail closed until a separately reviewed recovery.
            self._head = WitnessHead(head.epoch + 1, head.digest, operation_id)

    def finalize(self, *, operation_id: str, digest: str) -> None:
        _digest(digest)
        with self._lock:
            head = self._require()
            if head.pending != operation_id:
                raise WitnessUnavailable('unknown witness operation')
            self._head = WitnessHead(head.epoch, digest, None)


def _digest(value: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
            c not in '0123456789abcdef' for c in value):
        raise ValueError('invalid digest')


def authority_fingerprint(db) -> str:
    """Deterministic digest of the SEC-002 security state, including audit.

    Caller MUST serialize all authority mutations and hold a stable database
    snapshot. A SHA hash in-process is not authenticated evidence on its own.
    """
    tables = {
        'authority_config': ('singleton', 'issuer', 'audience', 'active_kid'),
        'signing_keys': ('kid', 'status'),
        'grants': ('jti', 'body_json', 'key_id', 'owner', 'subject',
                   'used', 'max_uses', 'revoked'),
        'audit_log': ('seq', 'event', 'jti', 'actor', 'occurred_at'),
    }
    contents = []
    for table, columns in tables.items():
        names = ','.join(columns)
        # SQL identifiers are exclusively hardcoded in this module.
        rows = db.execute(f'SELECT {names} FROM {table} ORDER BY {columns[0]}').fetchall()
        contents.append((table, rows))
    message = json.dumps(contents, sort_keys=True, separators=(',', ':'),
                         allow_nan=False, ensure_ascii=True).encode('ascii')
    return hashlib.sha256(message).hexdigest()


R = TypeVar('R')


class WitnessedAuthority:
    """Fail-closed research wrapper over SEC-002 DurableCapabilityAuthority.

    Only works if ALL authority writers go through one fenced service boundary.
    Direct database/API access bypasses this wrapper. No production claims.
    """

    def __init__(self, authority, witness: MonotonicWitness):
        self.authority = authority
        self.witness = witness

    def initialize_empty_genesis(self) -> None:
        """Provision only a *fresh empty* authority under trusted operator control.

        Never run this to repair a restored database or lost witness.
        """
        db = self.authority.db
        if (db.execute('SELECT COUNT(*) FROM grants').fetchone()[0] != 0
                or db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0] != 0
                or db.execute('SELECT COUNT(*) FROM signing_keys').fetchone()[0] != 1):
            raise WitnessUnavailable('not a fresh authority')
        self.witness.provision_empty_authority(authority_fingerprint(db))

    def verify_current(self) -> WitnessHead:
        head = self.witness.head()
        if head.pending is not None or head.digest != authority_fingerprint(self.authority.db):
            raise WitnessUnavailable('authority rollback, divergence or pending mutation')
        return head

    def _mutate(self, operation_id: str, effect: Callable[[], R]) -> R:
        previous = self.verify_current()
        self.witness.begin(expected=previous, operation_id=operation_id)
        # Deliberately do not clear witness.pending on failure: a crash after a
        # DB commit must not allow stale authority state to be used.
        result = effect()
        self.witness.finalize(operation_id=operation_id,
                              digest=authority_fingerprint(self.authority.db))
        return result

    def issue(self, op_id: str, *args, **kwargs) -> str:
        return self._mutate(op_id, lambda: self.authority.issue(*args, **kwargs))

    def revoke(self, op_id: str, *args, **kwargs) -> None:
        self._mutate(op_id, lambda: self.authority.revoke(*args, **kwargs))

    def authorize(self, op_id: str, *args, **kwargs) -> str:
        return self._mutate(op_id, lambda: self.authority.authorize(*args, **kwargs))

    def rotate(self, op_id: str, *args, **kwargs) -> None:
        self._mutate(op_id, lambda: self.authority.rotate(*args, **kwargs))

    def revoke_key(self, op_id: str, *args, **kwargs) -> None:
        self._mutate(op_id, lambda: self.authority.revoke_key(*args, **kwargs))
