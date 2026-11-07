"""Research W3 signed capability gateway integration tests."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_guard import AuthorizedWorldAction, GuardedWorldGateway
from openworld_superkernel.world_fixture import (
    Action, Agent, Weather, create_world, verify_replay,
)

TEST_KEY = b'synthetic world gateway HMAC test key never deploy anywhere'


class TestGuardedWorldGateway(unittest.TestCase):
    def setUp(self):
        self.principal = 'user-one'
        self.authority = CapabilityAuthority(TEST_KEY, issuer='test', audience='world')
        self.gateway = GuardedWorldGateway(self.authority,
                                            authenticated_principal=lambda: self.principal)
        self.world = create_world((
            Agent('a1', 'owner-one', 'r', 7),
            Agent('a2', 'owner-one', 'r', 2),
            Agent('b1', 'owner-two', 'r', 5),
        ), (('a1', 'a2'), ('a2', 'b1')), seed=2026)
        now = int(time.time())
        self.start, self.end = now - 10, now + 120

    def grant(self, *, owner='owner-one', resource='a1', action='write_agent',
              principal='user-one'):
        return self.authority.issue(principal=principal, owner=owner,
                                    resource=resource, action=action,
                                    valid_from=self.start, expires_at=self.end)

    def action(self, *, actor='a1', target='a2', kind='transfer', amount=1,
               principal='owner-one', request_id='req-1', owner='owner-one',
               token_resource='a1', caller='user-one'):
        action = Action(request_id=request_id, tick=self.world.tick,
                        principal=principal, actor=actor, target=target,
                        kind=kind, amount=amount)
        return AuthorizedWorldAction(
            action,
            self.grant(owner=owner, resource=token_resource,
                       action='write_agent', principal=caller),
        )

    def test_authorized_same_owner_transfer_and_replay(self):
        result = self.gateway.advance(self.world, actions=(self.action(),))
        self.assertEqual(result.accepted, ('req-1',))
        self.assertEqual(dict(result.world.balances)['a1'], 6)
        self.assertEqual(dict(result.world.balances)['a2'], 3)
        self.assertTrue(verify_replay(self.world, result.world))

    def test_cross_owner_transfer_denied(self):
        entry = self.action(actor='a2', target='b1', token_resource='a2')
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world, actions=(entry,))
        self.assertEqual(self.world.tick, 0)

    def test_cross_owner_signal_denied(self):
        entry = self.action(actor='a2', target='b1', token_resource='a2',
                            kind='signal', amount=0)
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world, actions=(entry,))

    def test_wrong_principal_token_denied(self):
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world, actions=(self.action(caller='attacker'),))

    def test_wrong_resource_token_denied(self):
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world, actions=(self.action(token_resource='a2'),))

    def test_wrong_owner_claim_denied(self):
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world,
                                 actions=(self.action(principal='owner-two'),))

    def test_revoked_token_denied(self):
        item = self.action()
        from json import loads
        nonce = loads(item.signed_capability)['body']['nonce']
        self.authority.revoke(nonce)
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world, actions=(item,))

    def test_all_or_none_on_later_invalid_action(self):
        okay = self.action(request_id='first')
        denied = self.action(request_id='second', token_resource='wrong')
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world, actions=(okay, denied))
        self.assertEqual(self.world.tick, 0)
        self.assertEqual(len(self.world.events), 0)

    def test_authorized_observation(self):
        grant = self.grant(resource='a1', action='read_world')
        view = self.gateway.observe(self.world, agent_id='a1', signed_capability=grant)
        self.assertEqual(view.agent_id, 'a1')
        self.assertEqual(view.balance, 7)
        with self.assertRaises(PermissionError):
            self.gateway.observe(self.world, agent_id='a2', signed_capability=grant)

    def test_observation_denies_other_owner(self):
        grant = self.grant(resource='a1', action='read_world')
        with self.assertRaises(PermissionError):
            self.gateway.observe(self.world, agent_id='b1', signed_capability=grant)

    def test_default_empty_tick_allowed_only_by_trusted_host(self):
        state = self.gateway.advance(self.world, actions=(), external=(Weather('r', 'rain'),))
        self.assertEqual(state.world.tick, 1)
        self.assertEqual(dict(state.world.weather)['r'], 'rain')
        self.assertTrue(verify_replay(self.world, state.world))

    def test_absent_principal_denied(self):
        self.principal = ''
        with self.assertRaises(PermissionError):
            self.gateway.advance(self.world, actions=(self.action(),))


if __name__ == '__main__':
    unittest.main()
