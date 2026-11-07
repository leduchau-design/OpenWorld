"""P0-free, opt-in W2 population/genotype mathematical *research* tests."""
import hashlib
import math
from pathlib import Path
import sys
import unittest
from dataclasses import FrozenInstanceError, replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.population_repr import (
    AgentGenome, PopulationPoint, empirical_cf, make_genome, mutate_genome,
    sketch_population,
)

DIGEST = "sha256:" + hashlib.sha256(b"experimental-policy").hexdigest()


class CharacteristicSketchTests(unittest.TestCase):
    def test_zero_frequency_is_exactly_one(self):
        self.assertEqual(empirical_cf(((0., 1.), (1., 0.)), (0., 0.)), (1., 0.))

    def test_conjugate_symmetry(self):
        points = ((0.25, 1.), (2., 0.), (-3., 2.))
        re1, im1 = empirical_cf(points, (0.8, -0.5))
        re2, im2 = empirical_cf(points, (-0.8, 0.5))
        self.assertAlmostEqual(re1, re2, places=12)
        self.assertAlmostEqual(im1, -im2, places=12)

    def test_bounded_modulus(self):
        re, im = empirical_cf(((0.,), (3.,), (6.,)), (2.,))
        self.assertLessEqual(math.hypot(re, im), 1.000000000001)

    def test_empirical_convolution_identity_for_independent_samples(self):
        # Full pairwise empirical convolution, NOT same-index correlated sums.
        left = ((-1.,), (0.5,))
        right = ((2.,), (4.,), (6.,))
        sums = tuple((x[0] + y[0],) for x in left for y in right)
        a, b = empirical_cf(left, (0.8,))
        c, d = empirical_cf(right, (0.8,))
        p, q = empirical_cf(sums, (0.8,))
        self.assertAlmostEqual(p, a*c - b*d)
        self.assertAlmostEqual(q, a*d + b*c)

    def test_finite_frequency_aliasing_is_a_known_negative(self):
        # ECF at one frequency cannot identify every distinct distribution.
        left = empirical_cf(((0.,),), (2 * math.pi,))
        right = empirical_cf(((1.,),), (2 * math.pi,))
        self.assertAlmostEqual(left[0], right[0])
        self.assertAlmostEqual(left[1], right[1], places=12)

    def test_marginal_signature_fails_to_capture_time_order(self):
        a = empirical_cf(((0.,), (1.,), (0.,)), (1.,))
        b = empirical_cf(((1.,), (0.,), (0.,)), (1.,))
        self.assertEqual(a, b)

    def test_mixed_dimension_and_nonfinite_input_rejected(self):
        for args in [(((1., 2.),), (1.,)),
                     (((float("nan"),),), (1.,)),
                     (((1.,),), (float("inf"),)),
                     ((), (1.,))]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                empirical_cf(*args)

    def test_grouped_sketch_avoids_global_mean_collapse(self):
        points = (
            PopulationPoint("builder", "north", (0.,)),
            PopulationPoint("builder", "north", (0.,)),
            PopulationPoint("builder", "south", (2.,)),
            PopulationPoint("builder", "south", (2.,)),
            PopulationPoint("trader", "north", (7.,)),
        )
        out = sketch_population(points, ((0.,), (1.,)))
        self.assertEqual([(x.role, x.region, x.count) for x in out],
                         [("builder", "north", 2), ("builder", "south", 2)])
        self.assertNotAlmostEqual(out[0].characteristic[1][0],
                                  out[1].characteristic[1][0])
        self.assertTrue(all(not hasattr(x, "agent_id") for x in out))

    def test_bad_frequency_and_small_group_inputs_rejected(self):
        with self.assertRaises(ValueError):
            sketch_population([], ((0.,), (1., 0.)))
        with self.assertRaises(ValueError):
            sketch_population([], ((1.,),), min_group_size=1)
        with self.assertRaises(ValueError):
            sketch_population([PopulationPoint("unknown", "north", (1.,))],
                              ((1.,),))
        with self.assertRaises(ValueError):
            sketch_population([PopulationPoint("builder", "north", (1., 2.))],
                              ((1.,),))

    def test_group_sketch_empty_on_only_singletons(self):
        self.assertEqual(
            sketch_population([PopulationPoint("builder", "north", (0.,))],
                              ((0.,),)), ())


class GenomeTests(unittest.TestCase):
    def setUp(self):
        self.parent = make_genome(
            "explorer", "rules", DIGEST,
            {"risk": 50, "curiosity": 80, "cooperation": 30},
        )

    def test_deterministic_canonical_genome(self):
        same = make_genome("explorer", "rules", DIGEST,
                           {"cooperation": 30, "curiosity": 80, "risk": 50})
        self.assertEqual(self.parent, same)
        self.assertTrue(self.parent.genome_id.startswith("sha256:"))
        self.assertEqual(self.parent.generation, 0)

    def test_mutation_is_bounded_seeded_and_lineaged(self):
        child = mutate_genome(self.parent, seed=2026, step=5)
        self.assertEqual(child, mutate_genome(self.parent, seed=2026, step=5))
        self.assertNotEqual(child.genome_id, self.parent.genome_id)
        self.assertEqual(child.parent_genome_id, self.parent.genome_id)
        self.assertEqual(child.generation, 1)
        self.assertEqual(child.policy_digest, self.parent.policy_digest)
        changed = [k for k in dict(self.parent.traits)
                   if dict(self.parent.traits)[k] != dict(child.traits)[k]]
        self.assertEqual(len(changed), 1)
        self.assertEqual(abs(dict(child.traits)[changed[0]] -
                             dict(self.parent.traits)[changed[0]]), 5)

    def test_genome_has_no_owner_capabilities_memory_or_model_weights(self):
        self.assertFalse(any(hasattr(self.parent, key) for key in
                             ("owner_id", "agent_id", "capabilities",
                              "memory", "weights", "session_token")))
        with self.assertRaises(FrozenInstanceError):
            self.parent.role = "trader"

    def test_tampering_with_content_address_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(self.parent, genome_id="sha256:" + "0" * 64)
        with self.assertRaises(ValueError):
            replace(self.parent, traits=(("risk", 1),))

    def test_invalid_traits_and_policy_digest_rejected(self):
        with self.assertRaises(ValueError):
            make_genome("explorer", "rules", "untrusted-model",
                        {"curiosity": 50})
        for traits in ({"curiosity": -1}, {"risk": 101}, {"trust_admin": 2},
                       {"risk": True}):
            with self.subTest(traits=traits), self.assertRaises(ValueError):
                make_genome("explorer", "rules", DIGEST, traits)

    def test_invalid_mutation_step_rejected(self):
        with self.assertRaises(ValueError):
            mutate_genome(self.parent, seed=1, step=0)
        with self.assertRaises(ValueError):
            mutate_genome(self.parent, seed=-1)
        with self.assertRaises(ValueError):
            make_genome("warrior", "rules", DIGEST, {"risk": 50})


if __name__ == "__main__":
    unittest.main()
