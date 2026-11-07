"""Research-only provenance anchoring and scoped capability checks.

NO external issuer is deployed here. The verification key must be controlled
outside the mutable database and outside any compromised application runtime.
Authenticating a capability does not authenticate an observed event's source.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ZERO_HASH = '0' * 64
TOKEN_VERSION = 'openworld-capability-v1'
ANCHOR_VERSION = 'openworld-ledger-anchor-v1'
ALLOWED_ACTIONS = frozenset({'read_state', 'read_event', 'write_agent', 'read_world'})


class TrustBoundaryError(ValueError):
    """The offered claim or evidence fails its specified trust boundary."""


def _key(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ValueError('A key of at least 32 bytes is required')
    return value


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _unique_keys(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise TrustBoundaryError('duplicate JSON object key')
        result[name] = value
    return result


def _decode(value: str | bytes) -> dict:
    if not isinstance(value, (str, bytes)) or len(value) > 8192:
        raise TrustBoundaryError('invalid or oversized JSON envelope')
    try:
        parsed = json.loads(value, object_pairs_hook=_unique_keys,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                TrustBoundaryError('nonfinite JSON value')))
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise TrustBoundaryError('invalid JSON envelope') from exc
    if not isinstance(parsed, dict):
        raise TrustBoundaryError('expected JSON object')
    return parsed


def _hmac_hex(payload: dict, key: bytes) -> str:
    return hmac.new(_key(key), _canonical(payload), hashlib.sha256).hexdigest()


def _verify_envelope(data: str | bytes, key: bytes, kind: str) -> dict:
    wrapper = _decode(data)
    if set(wrapper) != {'body', 'signature'} or not isinstance(wrapper['body'], dict):
        raise TrustBoundaryError('invalid signed envelope')
    signature = wrapper['signature']
    if (not isinstance(signature, str) or len(signature) != 64
            or any(c not in '0123456789abcdef' for c in signature)):
        raise TrustBoundaryError('invalid signature encoding')
    if wrapper['body'].get('version') != kind:
        raise TrustBoundaryError('invalid envelope version')
    if not hmac.compare_digest(_hmac_hex(wrapper['body'], key), signature):
        raise TrustBoundaryError('signature mismatch')
    return wrapper['body']


def _sign_envelope(body: dict, key: bytes) -> str:
    return _canonical({'body': body, 'signature': _hmac_hex(body, key)}).decode('ascii')


@dataclass(frozen=True)
class Capability:
    issuer: str
    audience: str
    principal: str
    owner: str
    resource: str
    action: str
    valid_from: int
    expires_at: int
    nonce: str

    def check(self) -> None:
        for value in (self.issuer, self.audience, self.principal,
                      self.owner, self.resource, self.nonce):
            if not isinstance(value, str) or not value or len(value) > 256:
                raise TrustBoundaryError('invalid capability identity or resource')
        if self.action not in ALLOWED_ACTIONS:
            raise TrustBoundaryError('unknown capability action')
        if (type(self.valid_from) is not int or type(self.expires_at) is not int
                or self.expires_at <= self.valid_from
                or self.expires_at - self.valid_from > 3600):
            raise TrustBoundaryError('invalid capability lifetime')

    def body(self) -> dict:
        self.check()
        return {'version': TOKEN_VERSION, 'issuer': self.issuer,
                'audience': self.audience, 'principal': self.principal,
                'owner': self.owner, 'resource': self.resource,
                'action': self.action, 'valid_from': self.valid_from,
                'expires_at': self.expires_at, 'nonce': self.nonce}


class CapabilityAuthority:
    """Symmetric-key RESEARCH issuer/verifier, not an identity provider.

    The caller's principal must be authenticated independently by the host.
    The in-memory revocation set is NOT durable across process restarts.
    """

    def __init__(self, key: bytes, *, issuer: str, audience: str):
        self.key = _key(key)
        self.issuer = issuer
        self.audience = audience
        self.revoked_nonces: set[str] = set()
        if not issuer or not audience:
            raise ValueError('issuer and audience required')

    def issue(self, *, principal: str, owner: str, resource: str,
              action: str, valid_from: int, expires_at: int,
              nonce: str | None = None) -> str:
        grant = Capability(self.issuer, self.audience, principal, owner,
                           resource, action, valid_from, expires_at,
                           nonce if nonce is not None else secrets.token_hex(16))
        return _sign_envelope(grant.body(), self.key)

    def verify(self, token: str, *, authenticated_principal: str,
               owner: str, resource: str, action: str,
               now: int | None = None) -> Capability:
        body = _verify_envelope(token, self.key, TOKEN_VERSION)
        expected = {'version', 'issuer', 'audience', 'principal', 'owner',
                    'resource', 'action', 'valid_from', 'expires_at', 'nonce'}
        if set(body) != expected:
            raise TrustBoundaryError('unrecognized capability fields')
        grant = Capability(body['issuer'], body['audience'], body['principal'],
                           body['owner'], body['resource'], body['action'],
                           body['valid_from'], body['expires_at'], body['nonce'])
        grant.check()
        clock = int(time.time()) if now is None else now
        if type(clock) is not int:
            raise TrustBoundaryError('invalid clock')
        if grant.issuer != self.issuer or grant.audience != self.audience:
            raise TrustBoundaryError('wrong issuing authority or audience')
        if (grant.principal != authenticated_principal or grant.owner != owner
                or grant.resource != resource or grant.action != action):
            raise PermissionError('capability does not match requested resource')
        if grant.nonce in self.revoked_nonces:
            raise PermissionError('revoked capability')
        if not grant.valid_from <= clock < grant.expires_at:
            raise PermissionError('capability not currently valid')
        return grant

    def revoke(self, nonce: str) -> None:
        if not isinstance(nonce, str) or not nonce:
            raise ValueError('nonce required')
        self.revoked_nonces.add(nonce)


def _record_blob(owner: str, agent: str, row: tuple) -> bytes:
    seq, event_id, provenance, kind, payload, digest = row
    if (type(seq) is not int or seq < 1 or not isinstance(payload, bytes)
            or any(not isinstance(v, str) for v in (event_id, provenance, kind, digest))):
        raise TrustBoundaryError('malformed exact record')
    actual = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual, digest):
        raise TrustBoundaryError('exact event payload digest mismatch')
    # Full data coverage is achieved through hash of exact payload and metadata.
    return _canonical({'owner': owner, 'agent': agent, 'sequence': seq,
                       'event_id': event_id, 'provenance': provenance,
                       'event_type': kind, 'payload_sha256': actual})


def ledger_snapshot(db: sqlite3.Connection, *, owner: str, agent: str) -> dict:
    """Full scan of exact-event records. O(n) even with a stored checkpoint."""
    if not owner or not agent:
        raise ValueError('owner and agent required')
    rows = db.execute('SELECT seq,event_id,provenance,event_type,payload,payload_hash '
                      'FROM exact_events WHERE owner_id=? AND agent_id=? ORDER BY seq',
                      (owner, agent))
    tip = ZERO_HASH
    count = 0
    last_seq = 0
    for row in rows:
        if row[0] <= last_seq:
            raise TrustBoundaryError('non-increasing exact event sequence')
        event_hash = hashlib.sha256(_record_blob(owner, agent, row)).digest()
        tip = hashlib.sha256(bytes.fromhex(tip) + event_hash).hexdigest()
        count += 1
        last_seq = row[0]
    return {'version': ANCHOR_VERSION, 'owner': owner, 'agent': agent,
            'count': count, 'last_sequence': last_seq, 'head_sha256': tip}


def capture_anchor(db: sqlite3.Connection, *, owner: str, agent: str,
                   external_signing_key: bytes) -> str:
    """Return a signed snapshot to be stored OUTSIDE the mutable database.

    The code cannot ensure the caller actually exports it. Sign only after an
    authoritative stable snapshot is captured and trusted by the operator.
    """
    snapshot = ledger_snapshot(db, owner=owner, agent=agent)
    return _sign_envelope(snapshot, external_signing_key)


def verify_anchor(db: sqlite3.Connection, *, signed_anchor: str,
                  external_verification_key: bytes, owner: str, agent: str) -> bool:
    """Verify HMAC and exact CURRENT ledger equality; new records fail closed.

    Same key signs/verifies, so this is NOT public non-repudiation or source
    authentication. No claim about unseen events prior to the first anchor.
    """
    data = _verify_envelope(signed_anchor, external_verification_key, ANCHOR_VERSION)
    if set(data) != {'version', 'owner', 'agent', 'count',
                     'last_sequence', 'head_sha256'}:
        raise TrustBoundaryError('invalid anchor body')
    if data['owner'] != owner or data['agent'] != agent:
        raise PermissionError('cross-stream anchor access denied')
    if (type(data['count']) is not int or type(data['last_sequence']) is not int
            or type(data['head_sha256']) is not str):
        raise TrustBoundaryError('invalid anchor data types')
    if ledger_snapshot(db, owner=owner, agent=agent) != data:
        raise TrustBoundaryError('ledger diverges from externally signed anchor')
    return True


def online_backup(source: sqlite3.Connection, target: str | Path) -> None:
    """Create SQLite's online consistent backup; caller protects target.

    Explicitly refuses to overwrite an existing backup. Does not certify
    filesystem durability, key management, encryption or offsite custody.
    """
    destination = Path(target)
    if destination.exists():
        raise FileExistsError('refuse overwrite of backup')
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(destination)) as backup:
            source.backup(backup)
            result = backup.execute('PRAGMA integrity_check').fetchone()
            if result != ('ok',):
                raise TrustBoundaryError('SQLite backup integrity check failed')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


class ScopedMemoryReader:
    """Enforce a verified grant when reading an underlying HM-P1e store.

    The host MUST pass a separately authenticated principal. The authority's
    symmetric key and revocation state are demonstration components only.
    """

    def __init__(self, store, authority: CapabilityAuthority,
                 authenticated_principal: Callable[[], str]):
        self.store = store
        self.authority = authority
        self.authenticated_principal = authenticated_principal

    def read_state(self, token: str, *, owner: str, agent: str) -> dict:
        self.authority.verify(token, authenticated_principal=self.authenticated_principal(),
                              owner=owner, resource=agent, action='read_state')
        return self.store.get_state(owner_id=owner, agent_id=agent,
                                    requester_owner_id=owner)

    def read_event(self, token: str, *, owner: str, event_id: str) -> bytes | None:
        self.authority.verify(token, authenticated_principal=self.authenticated_principal(),
                              owner=owner, resource=event_id, action='read_event')
        return self.store.exact_event(event_id, requester_owner_id=owner)
