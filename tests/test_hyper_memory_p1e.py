"""Contracts for experimental cost-aware HyperMemory (independent of benchmarks)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openworld_superkernel.memory_contracts import MemoryEvent, Provenance
from openworld_superkernel.hyper_memory_p1e import (
    ConflictingRetryError, EvidenceIntegrityError, HyperMemoryP1e,
    Observation, StaleRetryError,
)


def observation(seq, owner="owner-a", agent="agent-a", outcome=1,
                provenance=Provenance.SIMULATED, protected=False, kind="telemetry"):
    return Observation(
        MemoryEvent(
            event_id=f"{agent}:step-{seq}", owner_id=owner, event_type=kind,
            provenance=provenance, payload=f"payload:{seq}".encode(),
            reconstructable=True, protected=protected,
        ),
        agent_id=agent, sequence_number=seq, outcome=outcome,
    )


class HyperMemoryP1eTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.sqlite"
        self.db = HyperMemoryP1e(self.path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def state(self, agent="agent-a", owner="owner-a"):
        return self.db.get_state(owner_id=owner, agent_id=agent, requester_owner_id=owner)

    def test_empty_prior(self):
        self.assertEqual(self.db.predict(owner_id="owner-a", agent_id="agent-a",
                                         requester_owner_id="owner-a"), (0.5, "static"))

    def test_update_persists_exactly_once(self):
        item = observation(1)
        self.assertEqual(self.db.apply_batch([item], requester_owner_id="owner-a"), 1)
        self.assertEqual(self.db.apply_batch([item], requester_owner_id="owner-a"), 0)
        self.assertEqual(self.state()["n"], 1)

    def test_subsequent_state_reuses_identity(self):
        self.db.apply_batch([observation(i) for i in (1, 2, 3)], requester_owner_id="owner-a")
        self.assertEqual(self.state()["n"], 3)
        self.assertEqual(self.state()["successes"], 3)

    def test_different_agents_isolated(self):
        self.db.apply_batch([observation(1, agent="one"),
                             observation(1, agent="two", outcome=0)],
                            requester_owner_id="owner-a")
        self.assertEqual(self.state("one")["successes"], 1)
        self.assertEqual(self.state("two")["successes"], 0)

    def test_out_of_order_rejected_atomically(self):
        with self.assertRaises(ValueError):
            self.db.apply_batch([observation(1), observation(3)], requester_owner_id="owner-a")
        self.assertEqual(self.state()["n"], 0)

    def test_old_retry_fails_closed(self):
        self.db.apply_batch([observation(1), observation(2)], requester_owner_id="owner-a")
        with self.assertRaises(StaleRetryError):
            self.db.apply_batch([observation(1)], requester_owner_id="owner-a")
        self.assertEqual(self.state()["n"], 2)

    def test_conflicting_latest_retry_rejected(self):
        self.db.apply_batch([observation(1)], requester_owner_id="owner-a")
        with self.assertRaises(ConflictingRetryError):
            self.db.apply_batch([observation(1, outcome=0)], requester_owner_id="owner-a")

    def test_failure_before_commit_rolls_back(self):
        with self.assertRaises(RuntimeError):
            self.db.apply_batch([observation(1, protected=True)],
                                requester_owner_id="owner-a", inject_failure=True)
        self.assertEqual(self.state()["n"], 0)
        self.assertIsNone(self.db.exact_event("agent-a:step-1", requester_owner_id="owner-a"))

    def test_protected_event_retains_exact_bytes(self):
        item = observation(1, protected=True)
        self.db.apply_batch([item], requester_owner_id="owner-a")
        self.assertEqual(self.db.exact_event(item.event.event_id, requester_owner_id="owner-a"),
                         item.event.payload)

    def test_observed_event_retained_even_when_reconstructable(self):
        item = observation(1, provenance=Provenance.OBSERVED_RECORDED)
        self.db.apply_batch([item], requester_owner_id="owner-a")
        self.assertEqual(self.db.exact_event(item.event.event_id, requester_owner_id="owner-a"),
                         item.event.payload)

    def test_cross_owner_write_denied(self):
        with self.assertRaises(PermissionError):
            self.db.apply_batch([observation(1, owner="owner-b")],
                                requester_owner_id="owner-a")
        self.assertEqual(self.state("agent-a", "owner-b")["n"], 0)

    def test_cross_owner_read_denied(self):
        with self.assertRaises(PermissionError):
            self.db.get_state(owner_id="owner-a", agent_id="agent-a",
                              requester_owner_id="owner-b")

    def test_cross_owner_exact_event_indistinguishable_from_absent(self):
        self.db.apply_batch([observation(1, protected=True)], requester_owner_id="owner-a")
        self.assertIsNone(
            self.db.exact_event("agent-a:step-1", requester_owner_id="owner-b"))
        self.assertIsNone(
            self.db.exact_event("nonexistent", requester_owner_id="owner-b"))

    def test_same_event_id_in_different_owner_namespaces(self):
        first = observation(1, owner="owner-a", protected=True)
        second = observation(1, owner="owner-b", protected=True)
        self.assertEqual(first.event.event_id, second.event.event_id)
        self.db.apply_batch([first], requester_owner_id="owner-a")
        self.db.apply_batch([second], requester_owner_id="owner-b")
        self.assertEqual(self.db.exact_event(
            first.event.event_id, requester_owner_id="owner-a"), first.event.payload)
        self.assertEqual(self.db.exact_event(
            second.event.event_id, requester_owner_id="owner-b"), second.event.payload)
        with self.assertRaises(ValueError):
            self.db.exact_event(first.event.event_id, requester_owner_id="")

    def test_corrupt_exact_payload_is_detected(self):
        self.db.apply_batch([observation(1, protected=True)], requester_owner_id="owner-a")
        self.db.db.execute("UPDATE exact_events SET payload=X'FF' WHERE event_id=?",
                           ("agent-a:step-1",))
        with self.assertRaises(EvidenceIntegrityError):
            self.db.exact_event("agent-a:step-1", requester_owner_id="owner-a")

    def test_restart_restores_state_and_receipt(self):
        item = observation(1)
        self.db.apply_batch([item], requester_owner_id="owner-a")
        self.db.close()
        self.db = HyperMemoryP1e(self.path)
        self.assertEqual(self.db.apply_batch([item], requester_owner_id="owner-a"), 0)
        self.assertEqual(self.state()["n"], 1)

    def test_gate_stays_in_range(self):
        for seq in range(1, 121):
            self.db.apply_batch([observation(seq, outcome=int(seq % 3 != 0))],
                                requester_owner_id="owner-a")
        p, mode = self.db.predict(owner_id="owner-a", agent_id="agent-a",
                                  requester_owner_id="owner-a")
        self.assertGreaterEqual(p, 0)
        self.assertLessEqual(p, 1)
        self.assertIn(mode, {"static", "fast", "slow"})

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            Observation(observation(1).event, "agent-a", 1, 2)
        with self.assertRaises(ValueError):
            Observation(observation(1).event, "", 1, 1)
        with self.assertRaises(ValueError):
            Observation(observation(1).event, "agent-a", 0, 1)


if __name__ == "__main__":
    unittest.main()
