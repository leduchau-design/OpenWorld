"""Negative and positive tests for the isolated experimental W3 world fixture."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from openworld_superkernel.world_fixture import (
    Action, Agent, TickInput, Weather, advance, candidate_contacts,
    create_world, observe, seeded_signals, verify_replay,
)


class WorldFixtureTests(unittest.TestCase):
    def setUp(self):
        self.genesis = create_world((Agent('a', 'owner-a', 'north', 10),
                                     Agent('b', 'owner-b', 'north', 1),
                                     Agent('c', 'owner-c', 'south', 0),
                                     Agent('d', 'owner-d', 'south', 2)),
                                    (('a', 'b'), ('b', 'c')), seed=42)

    def act(self, request_id='1', actor='a', target='b', principal='owner-a',
            kind='transfer', amount=1, tick=0):
        return Action(request_id, tick, principal, actor, target, kind, amount)

    def test_sparse_contacts(self):
        self.assertEqual(candidate_contacts(self.genesis, ('a',)), (('a', 'b'),))
        self.assertEqual(candidate_contacts(self.genesis, ('b',)), (('b', 'a'), ('b', 'c')))
        self.assertEqual(candidate_contacts(self.genesis, ('d',)), ())

    def test_seeded_decisions_are_deterministic(self):
        a = seeded_signals(self.genesis, ('b', 'a'))
        b = seeded_signals(self.genesis, ('a', 'b'))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 2)

    def test_conservation_and_valid_neighbor_transfer(self):
        result = advance(self.genesis, TickInput(0, (self.act(amount=7),), ()))
        self.assertEqual(dict(result.world.balances), {'a': 3, 'b': 8, 'c': 0, 'd': 2})
        self.assertEqual(sum(dict(result.world.balances).values()), 13)
        self.assertEqual(result.world.events[0].provenance, 'SIMULATED')
        self.assertTrue(verify_replay(self.genesis, result.world))

    def test_deny_cross_owner_access_and_private_observation(self):
        bad = advance(self.genesis, TickInput(0, (self.act(principal='owner-b'),), ()))
        self.assertEqual(bad.rejected[0][1], 'unauthorized')
        self.assertEqual(bad.world.balances, self.genesis.balances)
        with self.assertRaises(PermissionError):
            observe(self.genesis, 'owner-b', 'a')
        visible = observe(self.genesis, 'owner-a', 'a')
        self.assertEqual(visible.neighbors, ('b',))
        self.assertFalse(hasattr(visible, 'owners'))
        self.assertFalse(hasattr(visible, 'all_balances'))

    def test_neighbor_required(self):
        out = advance(self.genesis, TickInput(0, (self.act(target='c'),), ()))
        self.assertEqual(out.rejected, (('1', 'not_neighbors'),))

    def test_conflicting_transfers_are_serialized(self):
        a = self.act(request_id='a', amount=8)
        b = self.act(request_id='b', amount=8)
        x = advance(self.genesis, TickInput(0, (b, a), ()))
        y = advance(self.genesis, TickInput(0, (a, b), ()))
        self.assertEqual(x.world.fingerprint(), y.world.fingerprint())
        self.assertEqual(x.accepted, ('a',))
        self.assertEqual(x.rejected[0][1], 'insufficient_resources')

    def test_duplicate_stale_and_unknown_kind_fail_closed(self):
        out = advance(self.genesis, TickInput(0, (self.act('a'), self.act('a'),
                    self.act('stale', tick=10), self.act('bad', kind='admin')), ()))
        self.assertEqual(out.accepted, ('a',))
        self.assertEqual(len(out.rejected), 3)
        second = advance(out.world, TickInput(1, (self.act('a', tick=1),), ()))
        self.assertEqual(second.rejected[0][1], 'duplicate_or_invalid_id')

    def test_missing_external_input_must_fail(self):
        with self.assertRaisesRegex(ValueError, 'external inputs missing'):
            advance(self.genesis, TickInput(0, (), None))

    def test_exogenous_weather_record_and_replay(self):
        state = advance(self.genesis, TickInput(0, (), (Weather('north', 'rain'),))).world
        self.assertEqual(dict(state.weather)['north'], 'rain')
        self.assertEqual(state.events[0].kind, 'weather.rain')
        self.assertEqual(observe(state, 'owner-a', 'a').weather, 'rain')
        self.assertEqual(observe(state, 'owner-c', 'c').weather, 'clear')
        self.assertTrue(verify_replay(self.genesis, state))

    def test_duplicate_exogenous_weather_denied(self):
        with self.assertRaisesRegex(ValueError, 'conflicting exogenous'):
            advance(self.genesis, TickInput(0, (), (Weather('north', 'rain'),
                                                   Weather('north', 'clear'))))

    def test_replay_detects_tampering(self):
        from dataclasses import replace
        world = advance(self.genesis, TickInput(0, (self.act(),), ())).world
        tampered = replace(world, balances=(('a', 999),) + world.balances[1:])
        with self.assertRaisesRegex(ValueError, 'replay diverged'):
            verify_replay(self.genesis, tampered)

    def test_signal_inbox_does_not_expose_unrelated_events(self):
        a = self.act('signal-a', kind='signal', amount=0)
        b = self.act('signal-b', actor='b', target='c', principal='owner-b',
                     kind='signal', amount=0)
        world = advance(self.genesis, TickInput(0, (a, b), ())).world
        self.assertEqual(observe(world, 'owner-b', 'b').inbox, (('a', 0),))
        self.assertEqual(observe(world, 'owner-c', 'c').inbox, (('b', 0),))
        self.assertEqual(observe(world, 'owner-d', 'd').inbox, ())

    def test_budget_and_invalid_genesis(self):
        with self.assertRaisesRegex(ValueError, 'action budget'):
            advance(self.genesis, TickInput(0, (self.act(),), ()), max_actions=0)
        with self.assertRaises(ValueError):
            create_world((Agent('a', 'o', 'r', 1), Agent('a', 'o', 'r', 2)), ())
        with self.assertRaises(ValueError):
            create_world((Agent('a', 'o', 'r', -1),), ())


if __name__ == '__main__':
    unittest.main()
