"""Atomicity, replay and provenance tests for the opt-in research ensemble."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from openworld_superkernel.hyper_memory_ensemble import (
    EnsembleHyperMemory, EnsembleStateCorrupted, IncompatibleMemoryPolicy,
)
from openworld_superkernel.hyper_memory_p1e import (
    ConflictingRetryError, HyperMemoryP1e, Observation, StaleRetryError,
)
from openworld_superkernel.memory_contracts import MemoryEvent, Provenance


def sample(sequence, *, agent='a', owner='owner', outcome=1, protected=False,
           provenance=Provenance.SIMULATED):
    return Observation(
        event=MemoryEvent(event_id=f'{agent}:{sequence}', owner_id=owner,
                          event_type='observation', provenance=provenance,
                          payload=f'contents-{sequence}'.encode(),
                          reconstructable=provenance == Provenance.SIMULATED,
                          protected=protected),
        agent_id=agent, sequence_number=sequence, outcome=outcome)


class EnsembleMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'ensemble.sqlite'
        self.db = EnsembleHyperMemory(self.path, eta=0.5)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def update(self, *events):
        return self.db.apply_batch(events, requester_owner_id='owner')

    def state(self, agent='a'):
        return self.db.get_ensemble_state(owner_id='owner', agent_id=agent,
                                          requester_owner_id='owner')

    def forecast(self, agent='a'):
        return self.db.predict(owner_id='owner', agent_id=agent,
                               requester_owner_id='owner')

    def test_initial_forecast_is_half(self):
        self.assertEqual(self.forecast(), (0.5, 'ensemble'))
        self.assertEqual(self.state()['steps'], 0)

    def test_atomic_state_and_ledger(self):
        item = sample(1, protected=True)
        self.assertEqual(self.update(item), 1)
        self.assertEqual(self.db.exact_event('a:1', requester_owner_id='owner'),
                         item.event.payload)
        self.assertEqual(self.state()['steps'], 1)
        self.assertAlmostEqual(self.state()['last_prequential_prediction'], 0.5)
        self.assertAlmostEqual(self.state()['cumulative_mix_brier'], 0.25)

    def test_prequential_prediction_not_leaked(self):
        first = self.forecast()[0]
        self.update(sample(1, outcome=0))
        self.assertEqual(self.state()['last_prequential_prediction'], first)
        self.assertEqual(self.forecast()[1], 'ensemble')
        self.assertNotEqual(self.forecast()[0], first)

    def test_rollback_all_three_lanes(self):
        with self.assertRaises(RuntimeError):
            self.db.apply_batch([sample(1, protected=True)],
                                requester_owner_id='owner', inject_failure=True)
        self.assertEqual(self.state()['steps'], 0)
        self.assertEqual(self.db.get_state(owner_id='owner', agent_id='a',
                                          requester_owner_id='owner')['seq'], 0)
        self.assertIsNone(self.db.exact_event('a:1', requester_owner_id='owner'))

    def test_batch_failure_rolls_back_earlier_agent(self):
        with self.assertRaises(ValueError):
            self.update(sample(1), sample(3))
        self.assertEqual(self.state()['steps'], 0)

    def test_latest_retry_exactly_once(self):
        item = sample(1)
        self.assertEqual(self.update(item), 1)
        self.assertEqual(self.update(item), 0)
        self.assertEqual(self.state()['steps'], 1)

    def test_conflicting_retry_rejected(self):
        self.update(sample(1))
        with self.assertRaises(ConflictingRetryError):
            self.update(sample(1, outcome=0))
        self.assertEqual(self.state()['steps'], 1)

    def test_stale_retry_rejected(self):
        self.update(sample(1), sample(2))
        with self.assertRaises(StaleRetryError):
            self.update(sample(1))

    def test_restart_preserves_predictions_and_weights(self):
        self.update(*(sample(i, outcome=i % 2) for i in range(1, 10)))
        before = (self.forecast(), self.state())
        self.db.close()
        self.db = EnsembleHyperMemory(self.path, eta=0.5)
        self.assertEqual((self.forecast(), self.state()), before)
        self.assertEqual(self.update(sample(9, outcome=1)), 0)

    def test_different_agents_independent(self):
        self.update(sample(1, agent='a', outcome=1), sample(1, agent='b', outcome=0))
        self.assertNotEqual(self.forecast('a'), self.forecast('b'))
        self.assertEqual(self.state('a')['steps'], self.state('b')['steps'])

    def test_owner_isolation_read(self):
        self.update(sample(1, protected=True))
        with self.assertRaises(PermissionError):
            self.db.get_ensemble_state(owner_id='owner', agent_id='a',
                                       requester_owner_id='intruder')
        with self.assertRaises(PermissionError):
            self.db.predict(owner_id='owner', agent_id='a',
                            requester_owner_id='intruder')

    def test_owner_isolation_write(self):
        with self.assertRaises(PermissionError):
            self.db.apply_batch([sample(1, owner='intruder')],
                                requester_owner_id='owner')
        self.assertEqual(self.state()['steps'], 0)

    def test_protected_and_observed_bytes(self):
        obs = sample(1, provenance=Provenance.OBSERVED_RECORDED)
        self.update(obs)
        self.assertEqual(self.db.exact_event('a:1', requester_owner_id='owner'),
                         obs.event.payload)
        self.assertEqual(self.state()['steps'], 1)

    def test_existing_baseline_requires_explicit_migration(self):
        self.db.close()
        self.path.unlink()
        base = HyperMemoryP1e(self.path)
        base.apply_batch([sample(1)], requester_owner_id='owner')
        base.close()
        with self.assertRaises(IncompatibleMemoryPolicy):
            EnsembleHyperMemory(self.path, eta=0.5)
        self.db = HyperMemoryP1e(self.path)
        self.assertEqual(self.db.get_state(owner_id='owner', agent_id='a',
                                          requester_owner_id='owner')['seq'], 1)

    def test_policy_is_pinned_across_restart(self):
        self.update(sample(1))
        with self.assertRaises(IncompatibleMemoryPolicy):
            EnsembleHyperMemory(self.path, eta=0.8)
        self.assertEqual(self.state()['steps'], 1)

    def test_corrupted_estimators_fail_closed(self):
        self.update(sample(1))
        self.db.db.execute('UPDATE ensemble_state SET state_json=?', ('{"steps":1}',))
        with self.assertRaises(EnsembleStateCorrupted):
            self.forecast()

    def test_corrupted_policy_version_rejected(self):
        self.update(sample(1))
        self.db.db.execute("UPDATE ensemble_state SET state_json=REPLACE(state_json, ?, ?)",
                           ('ow.hm-p1e.hedge.v1', 'ow.hm-p1e.hedge.v0'))
        with self.assertRaises(EnsembleStateCorrupted):
            self.forecast()

    def test_duplicate_event_id_rolls_back_ensemble(self):
        first = sample(1, protected=True)
        self.update(first)
        second = sample(1, agent='b', protected=True)
        # Force event-id collision; SQLite exact-event uniqueness must abort
        # both the base and the ensemble state updates for the second agent.
        collide = Observation(event=MemoryEvent(
            event_id=first.event.event_id, owner_id='owner',
            event_type='observation', provenance=Provenance.SIMULATED,
            payload=b'other', reconstructable=True, protected=True),
            agent_id='b', sequence_number=1, outcome=0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.update(collide)
        self.assertEqual(self.state('b')['steps'], 0)
        self.assertEqual(self.db.get_state(owner_id='owner',agent_id='b',
                                          requester_owner_id='owner')['seq'], 0)

    def test_external_legacy_writer_detected(self):
        base = HyperMemoryP1e(self.path)
        base.apply_batch([sample(1)], requester_owner_id='owner')
        base.close()
        with self.assertRaises(EnsembleStateCorrupted):
            self.forecast()

    def test_checkpoint_keeps_weights(self):
        self.update(*(sample(i) for i in range(1, 8)))
        prior = self.state()
        self.db.checkpoint()
        self.assertEqual(self.state(), prior)

    def test_batch_two_agents_atomic(self):
        self.update(sample(1, agent='a'), sample(1, agent='b', protected=True))
        self.assertEqual(self.state('a')['steps'], 1)
        self.assertEqual(self.state('b')['steps'], 1)
        self.assertEqual(self.db.exact_event('b:1', requester_owner_id='owner'), b'contents-1')


if __name__ == '__main__':
    unittest.main()
