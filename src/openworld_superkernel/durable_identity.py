"""SEC-002 offline reference: authenticated sessions and durable capabilities.

Security boundary: only a trusted process may hold IDP/issuer signing keys,
open this database, and call mutation APIs. This is NOT an identity provider,
network authentication service, or production-safe privilege boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Callable, Mapping


SESSION_VERSION = "openworld-session-v1"
GRANT_VERSION = "openworld-durable-capability-v1"
ACTIONS = frozenset({"read_state", "read_event", "read_world", "write_agent"})


class AuthenticationError(PermissionError):
    """The caller has no valid independent session proof."""


class AuthorizationError(PermissionError):
    """The authenticated caller lacks a currently usable capability."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError(f"invalid {name}")
    return value


def _key(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ValueError("signing key must be at least 32 bytes")
    return value


def _object_pairs(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON property")
        result[name] = value
    return result


def _encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      allow_nan=False, separators=(",", ":")).encode("ascii")


def _decode(token: str) -> dict:
    if not isinstance(token, str) or len(token) > 8192:
        raise ValueError("invalid token length")
    try:
        value = json.loads(token, object_pairs_hook=_object_pairs,
                           parse_constant=lambda v: (_ for _ in ()).throw(
                               ValueError("nonfinite JSON")))
    except (TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON token") from exc
    if not isinstance(value, dict) or set(value) != {"body", "signature"}:
        raise ValueError("invalid envelope")
    if not isinstance(value["body"], dict):
        raise ValueError("invalid body")
    signature = value["signature"]
    if not isinstance(signature, str) or len(signature) != 64 or any(
            ch not in "0123456789abcdef" for ch in signature):
        raise ValueError("invalid signature format")
    return value


def _sign(body: dict, key: bytes) -> str:
    mac = hmac.new(_key(key), _encode(body), hashlib.sha256).hexdigest()
    return _encode({"body": body, "signature": mac}).decode("ascii")


def _verify(token: str, key: bytes) -> dict:
    data = _decode(token)
    expected = hmac.new(_key(key), _encode(data["body"]), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, data["signature"]):
        raise AuthenticationError("bad token signature")
    return data["body"]


def _clock(clock: Callable[[], int]) -> int:
    now = clock()
    if type(now) is not int or now < 0:
        raise ValueError("trusted clock must return a nonnegative integer")
    return now


class LocalSessionVerifier:
    """Offline HMAC stand-in for an externally authenticated identity provider.

    A hostile client must never be allowed to call `issue`. Tokens are bearer
    credentials and cannot prove the physical identity of the user or agent.
    """

    def __init__(self, key: bytes, *, issuer: str, audience: str,
                 clock: Callable[[], int] = lambda: int(time.time())):
        self._key = _key(key)
        self.issuer = _text(issuer, "issuer")
        self.audience = _text(audience, "audience")
        self._clock = clock

    def issue(self, principal: str, *, lifetime: int = 120) -> str:
        principal = _text(principal, "principal")
        if type(lifetime) is not int or not 1 <= lifetime <= 300:
            raise ValueError("session lifetime must be 1..300 seconds")
        now = _clock(self._clock)
        body = {"v": SESSION_VERSION, "iss": self.issuer,
                "aud": self.audience, "sub": principal,
                "iat": now, "exp": now + lifetime,
                "sid": secrets.token_hex(16)}
        return _sign(body, self._key)

    def verify(self, token: str) -> str:
        try:
            body = _verify(token, self._key)
            if set(body) != {"v", "iss", "aud", "sub", "iat", "exp", "sid"}:
                raise ValueError("unexpected session claims")
            if body["v"] != SESSION_VERSION or body["iss"] != self.issuer:
                raise ValueError("untrusted session issuer")
            if body["aud"] != self.audience:
                raise ValueError("session audience mismatch")
            principal = _text(body["sub"], "principal")
            _text(body["sid"], "session ID")
            iat, exp, now = body["iat"], body["exp"], _clock(self._clock)
            if (type(iat) is not int or type(exp) is not int
                    or exp <= iat or exp - iat > 300
                    or not iat <= now < exp):
                raise ValueError("expired or invalid session")
            return principal
        except (ValueError, KeyError, TypeError, AuthenticationError) as exc:
            raise AuthenticationError("session authentication failed") from exc


class DurableCapabilityAuthority:
    """Research-only durable grants under separately signed session identity.

    The issuer's signing keys and session-verifier key MUST be injected from
    external custody. The database must be inaccessible to untrusted clients.
    Each authorization is an atomic grant-use consumption, not a transaction
    covering an external API/world mutation. The latter remains unsupported.
    """

    def __init__(self, path: str | Path, *, issuer: str, audience: str,
                 session_verifier: LocalSessionVerifier, keys: Mapping[str, bytes],
                 active_kid: str, clock: Callable[[], int] = lambda: int(time.time())):
        self.issuer = _text(issuer, "issuer")
        self.audience = _text(audience, "audience")
        self.sessions = session_verifier
        self.keys = {_text(kid, "key ID"): _key(key)
                     for kid, key in keys.items()}
        self.active_kid = _text(active_kid, "active key ID")
        self.clock = clock
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=15)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS authority_config (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                issuer TEXT NOT NULL, audience TEXT NOT NULL,
                active_kid TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signing_keys (
                kid TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('active','retired','revoked'))
            );
            CREATE TABLE IF NOT EXISTS grants (
                jti TEXT PRIMARY KEY, body_json TEXT NOT NULL,
                key_id TEXT NOT NULL REFERENCES signing_keys(kid),
                owner TEXT NOT NULL, subject TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                max_uses INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL, jti TEXT NOT NULL, actor TEXT NOT NULL,
                occurred_at INTEGER NOT NULL
            );
        """)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            config = self.db.execute(
                "SELECT issuer,audience,active_kid FROM authority_config WHERE singleton=1"
            ).fetchone()
            if config is None:
                if self.active_kid not in self.keys:
                    raise AuthenticationError("active signing key unavailable")
                self.db.execute("INSERT INTO authority_config VALUES(1,?,?,?)",
                                (self.issuer, self.audience, self.active_kid))
                self.db.execute("INSERT INTO signing_keys VALUES(?, 'active')",
                                (self.active_kid,))
            elif config != (self.issuer, self.audience, self.active_kid):
                raise AuthenticationError("authority configuration mismatch")
            self._require_key(self.active_kid, allow_retired=False)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            self.db.close()
            raise

    def _require_key(self, kid: str, *, allow_retired: bool = True) -> bytes:
        status_row = self.db.execute(
            "SELECT status FROM signing_keys WHERE kid=?", (kid,)
        ).fetchone()
        statuses = ("active", "retired") if allow_retired else ("active",)
        if status_row is None or status_row[0] not in statuses or kid not in self.keys:
            raise AuthenticationError("key unavailable or revoked")
        return self.keys[kid]

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "DurableCapabilityAuthority":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _audit(self, event: str, jti: str, actor: str) -> None:
        self.db.execute("INSERT INTO audit_log(event,jti,actor,occurred_at) VALUES(?,?,?,?)",
                        (event, jti, actor, _clock(self.clock)))

    def issue(self, owner_session: str, *, owner: str, subject: str,
              agent: str, resource: str, action: str, purpose: str,
              lifetime: int = 300, max_uses: int = 1) -> str:
        """Only a separately authenticated resource owner can issue a grant."""
        owner = _text(owner, "owner")
        subject = _text(subject, "subject")
        agent = _text(agent, "agent")
        resource = _text(resource, "resource")
        purpose = _text(purpose, "purpose")
        if self.sessions.verify(owner_session) != owner:
            raise AuthorizationError("issuer is not the authenticated owner")
        if action not in ACTIONS:
            raise ValueError("unknown action")
        if (type(lifetime) is not int or not 1 <= lifetime <= 3600
                or type(max_uses) is not int or not 1 <= max_uses <= 10):
            raise ValueError("invalid lifetime or grant use budget")
        now = _clock(self.clock)
        jti = secrets.token_hex(16)
        body = {"v": GRANT_VERSION, "iss": self.issuer, "aud": self.audience,
                "kid": self.active_kid, "jti": jti, "sub": subject,
                "owner": owner, "agent": agent, "res": resource,
                "act": action, "purpose": purpose, "nbf": now,
                "exp": now + lifetime, "max": max_uses}
        self.db.execute("BEGIN IMMEDIATE")
        try:
            key = self._require_key(self.active_kid, allow_retired=False)
            token = _sign(body, key)
            self.db.execute(
                "INSERT INTO grants(jti,body_json,key_id,owner,subject,max_uses) "
                "VALUES(?,?,?,?,?,?)",
                (jti, _encode(body).decode("ascii"), self.active_kid,
                 owner, subject, max_uses),
            )
            self._audit("issue", jti, owner)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return token

    def authorize(self, caller_session: str, grant_token: str, *, owner: str,
                  agent: str, resource: str, action: str, purpose: str) -> str:
        """Verify identity and consume one use, durably and atomically."""
        subject = self.sessions.verify(caller_session)
        wanted = {"owner": _text(owner, "owner"), "agent": _text(agent, "agent"),
                  "res": _text(resource, "resource"), "act": action,
                  "purpose": _text(purpose, "purpose")}
        if action not in ACTIONS:
            raise AuthorizationError("unknown action")
        try:
            token_data = _decode(grant_token)
            body = token_data["body"]
            if set(body) != {"v", "iss", "aud", "kid", "jti", "sub", "owner",
                             "agent", "res", "act", "purpose", "nbf", "exp", "max"}:
                raise ValueError("unexpected grant claims")
            kid, jti = _text(body["kid"], "key ID"), _text(body["jti"], "grant ID")
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthorizationError("malformed capability") from exc
        self.db.execute("BEGIN IMMEDIATE")
        try:
            key = self._require_key(kid)
            verified = _verify(grant_token, key)
            now = _clock(self.clock)
            if (verified["v"] != GRANT_VERSION or verified["iss"] != self.issuer
                    or verified["aud"] != self.audience or verified["sub"] != subject
                    or any(verified[field] != value for field, value in wanted.items())
                    or type(verified["nbf"]) is not int
                    or type(verified["exp"]) is not int
                    or type(verified["max"]) is not int
                    or verified["max"] not in range(1, 11)
                    or not verified["nbf"] <= now < verified["exp"]
                    or verified["exp"] - verified["nbf"] > 3600):
                raise AuthorizationError("expired or out-of-scope capability")
            record = self.db.execute(
                "SELECT body_json,key_id,owner,subject,used,max_uses,revoked "
                "FROM grants WHERE jti=?", (jti,)
            ).fetchone()
            if (record is None or record[0] != _encode(verified).decode("ascii")
                    or record[1:4] != (kid, owner, subject)
                    or record[5] != verified["max"] or record[6]
                    or record[4] >= record[5]):
                raise AuthorizationError("grant missing, revoked or exhausted")
            updated = self.db.execute(
                "UPDATE grants SET used=used+1 WHERE jti=? AND revoked=0 AND used<max_uses",
                (jti,),
            ).rowcount
            if updated != 1:
                raise AuthorizationError("grant use race or exhaustion")
            self._audit("consume", jti, subject)
            self.db.execute("COMMIT")
            return subject
        except BaseException as exc:
            self.db.execute("ROLLBACK")
            if isinstance(exc, AuthenticationError):
                raise AuthorizationError("grant signing key invalid") from exc
            raise

    def revoke(self, owner_session: str, *, grant_token: str) -> None:
        owner = self.sessions.verify(owner_session)
        try:
            body = _decode(grant_token)["body"]
            kid, jti = _text(body["kid"], "key ID"), _text(body["jti"], "grant ID")
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthorizationError("malformed revocation request") from exc
        self.db.execute("BEGIN IMMEDIATE")
        try:
            _verify(grant_token, self._require_key(kid))
            record = self.db.execute(
                "SELECT owner,body_json,revoked FROM grants WHERE jti=?",
                (jti,),
            ).fetchone()
            if (record is None or record[0] != owner
                    or record[1] != _encode(body).decode("ascii")):
                raise AuthorizationError("owner does not control this grant")
            if record[2] == 0:
                self.db.execute("UPDATE grants SET revoked=1 WHERE jti=?", (jti,))
                self._audit("revoke", jti, owner)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def rotate(self, *, new_kid: str, new_key: bytes) -> None:
        """Trusted administrator only: key custody is still external to this API."""
        new_kid = _text(new_kid, "key ID")
        new_key = _key(new_key)
        if new_kid in self.keys:
            raise ValueError("key ID cannot be reused")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self._require_key(self.active_kid, allow_retired=False)
            if self.db.execute("SELECT 1 FROM signing_keys WHERE kid=?",
                               (new_kid,)).fetchone():
                raise ValueError("historical key ID cannot be reused")
            self.db.execute("UPDATE signing_keys SET status='retired' WHERE kid=?",
                            (self.active_kid,))
            self.db.execute("INSERT INTO signing_keys VALUES(?, 'active')", (new_kid,))
            self.db.execute("UPDATE authority_config SET active_kid=? WHERE singleton=1",
                            (new_kid,))
            self._audit("rotate", new_kid, self.issuer)
            self.db.execute("COMMIT")
            self.keys[new_kid] = new_key
            self.active_kid = new_kid
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def revoke_key(self, kid: str) -> None:
        """Trusted administrator only; a revoked key can never be reactivated."""
        kid = _text(kid, "key ID")
        if kid == self.active_kid:
            raise ValueError("rotate before revoking the active key")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT status FROM signing_keys WHERE kid=?",
                               (kid,)).fetchone() is None:
                raise ValueError("unknown key ID")
            self.db.execute("UPDATE signing_keys SET status='revoked' WHERE kid=?", (kid,))
            self._audit("key_revoke", kid, self.issuer)
            self.db.execute("COMMIT")
            self.keys.pop(kid, None)
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def audit_events(self) -> tuple[tuple, ...]:
        """Locally persistent log; a compromised DB writer can still rewrite it."""
        return tuple(self.db.execute(
            "SELECT seq,event,jti,actor,occurred_at FROM audit_log ORDER BY seq"
        ).fetchall())


class AuthenticatedMemoryReader:
    """Owner-scoped research facade; do not expose the wrapped store to callers."""

    def __init__(self, authority: DurableCapabilityAuthority, store):
        self.authority = authority
        self._store = store

    def read_state(self, session: str, grant: str, *, owner: str, agent: str,
                   purpose: str) -> dict:
        self.authority.authorize(session, grant, owner=owner, agent=agent,
                                 resource=agent, action="read_state", purpose=purpose)
        return self._store.get_state(owner_id=owner, agent_id=agent,
                                     requester_owner_id=owner)

    def read_event(self, session: str, grant: str, *, owner: str, agent: str,
                   event_id: str, purpose: str) -> bytes | None:
        self.authority.authorize(session, grant, owner=owner, agent=agent,
                                 resource=event_id, action="read_event", purpose=purpose)
        # The underlying W1 API checks owner only. Verify agent binding here,
        # otherwise a grant nominally scoped to agent A could fetch agent B's
        # event under the same owner. This is NOT an atomic cross-DB read.
        row = self._store.db.execute(
            "SELECT agent_id FROM exact_events WHERE owner_id=? AND event_id=?",
            (owner, event_id),
        ).fetchone()
        if row is None:
            return None
        if row[0] != agent:
            raise AuthorizationError("event lies outside granted agent")
        return self._store.exact_event(event_id, requester_owner_id=owner)