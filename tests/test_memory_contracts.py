import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openworld_superkernel import MemoryEvent, MemoryRoute, Provenance, route_memory_event


class MemoryContractsTests(unittest.TestCase):
    def event(self, kind="observation", source=Provenance.OBSERVED_RECORDED,
              *, reconstructable=False, protected=False):
        return MemoryEvent("ev-1", "agent-1", kind, source, b"event", reconstructable, protected)

    def test_observed_event_is_exact(self):
        self.assertEqual(route_memory_event(self.event()), MemoryRoute.EXACT)

    def test_verified_event_is_exact(self):
        self.assertEqual(route_memory_event(self.event(source=Provenance.VERIFIED)), MemoryRoute.EXACT)

    def test_protected_event_is_exact(self):
        self.assertEqual(route_memory_event(self.event(source=Provenance.SIMULATED,
                      reconstructable=True, protected=True)), MemoryRoute.EXACT)

    def test_commitment_event_is_exact(self):
        self.assertEqual(route_memory_event(self.event(kind="promise", source=Provenance.SIMULATED,
                       reconstructable=True)), MemoryRoute.EXACT)

    def test_simulated_reconstructable_is_generative(self):
        self.assertEqual(route_memory_event(self.event(source=Provenance.SIMULATED,
                        reconstructable=True)), MemoryRoute.GENERATIVE)

    def test_simulated_unreconstructable_is_exact(self):
        self.assertEqual(route_memory_event(self.event(source=Provenance.SIMULATED)), MemoryRoute.EXACT)

    def test_inferred_routes_to_predictive(self):
        self.assertEqual(route_memory_event(self.event(source=Provenance.INFERRED)), MemoryRoute.PREDICTIVE)

    def test_missing_identity_rejected(self):
        with self.assertRaises(ValueError):
            MemoryEvent("", "agent", "obs", Provenance.SIMULATED, b"")

    def test_invalid_provenance_rejected(self):
        with self.assertRaises(TypeError):
            MemoryEvent("id", "agent", "obs", "verified", b"")

    def test_payload_must_be_bytes(self):
        with self.assertRaises(TypeError):
            MemoryEvent("id", "agent", "obs", Provenance.VERIFIED, "not bytes")


if __name__ == "__main__":
    unittest.main()
