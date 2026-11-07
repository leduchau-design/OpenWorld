"""W5 synthetic representation benchmark tests; no model API, agent training or data."""
from __future__ import annotations

import math
from pathlib import Path
import subprocess
import sys
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "src"))
from w5_population_repr import (METHODS, TASKS, TARGET, _percentile, features,
                                frequencies, labels, make_episode, run_case,
                                solve_ridge)
from openworld_superkernel.population_repr import PopulationPoint


class PopulationRepresentationBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.ecf, self.rff = frequencies(4, 4)

    def test_fixed_seed_episode_reproducible(self):
        self.assertEqual(make_episode(30, 4, 3101, "balanced"),
                         make_episode(30, 4, 3101, "balanced"))
        self.assertNotEqual(make_episode(30, 4, 3101, "balanced"),
                            make_episode(30, 4, 3102, "balanced"))

    def test_rare_group_is_explicitly_two_records(self):
        episode = make_episode(100, 4, 3101, "rare")
        self.assertEqual(sum((p.role, p.region) == TARGET for p in episode), 2)
        self.assertFalse(hasattr(episode[0], "owner_id"))

    def test_mean_and_histogram_are_exact_on_supported_targets(self):
        episode = make_episode(30, 4, 3101, "balanced")
        observed = labels(episode)
        group = features(episode, "group_mean", 4, self.ecf, self.rff)
        self.assertAlmostEqual((group[0] + 1) / 2, observed["mean"])
        hist = features(episode, "histogram8", 4, self.ecf, self.rff)
        self.assertAlmostEqual(hist[6] + hist[7], observed["tail"])

    def test_ecf_has_a_target_aligned_positive_control(self):
        episode = make_episode(30, 4, 3101, "balanced")
        ecf = features(episode, "ecf", 4, self.ecf, self.rff)
        self.assertAlmostEqual((ecf[0] + 1) / 2, labels(episode)["spectral"])
        self.assertLessEqual(math.hypot(ecf[0], ecf[1]), 1.000000001)

    def test_global_mean_erases_opposed_role_structure(self):
        def point(role, x):
            return PopulationPoint(role, "north", (x, 0., 0., 0.))
        left = (point("trader", 1.), point("trader", 1.),
                point("builder", -1.), point("builder", -1.))
        right = (point("trader", -1.), point("trader", -1.),
                 point("builder", 1.), point("builder", 1.))
        self.assertEqual(features(left, "global_mean", 4, self.ecf, self.rff),
                         features(right, "global_mean", 4, self.ecf, self.rff))
        self.assertNotEqual(features(left, "group_mean", 4, self.ecf, self.rff),
                            features(right, "group_mean", 4, self.ecf, self.rff))
        self.assertNotEqual(labels(left)["mean"], labels(right)["mean"])

    def test_temporal_permutation_not_identified(self):
        samples = [PopulationPoint("trader", "north", (x, 0., 0., 0.))
                   for x in (-1., 1., 0.)]
        original = tuple(samples)
        reordered = (samples[1], samples[0], samples[2])
        self.assertEqual(features(original, "ecf", 4, self.ecf, self.rff),
                         features(reordered, "ecf", 4, self.ecf, self.rff))
        self.assertNotEqual([p.features for p in original],
                            [p.features for p in reordered])

    def test_all_methods_have_fixed_width_and_no_private_fields(self):
        episode = make_episode(30, 4, 3101, "skewed")
        widths = {"no_summary": 0, "global_mean": 4, "group_mean": 4,
                  "histogram8": 8, "ecf": 8, "rff": 8}
        for method in METHODS:
            with self.subTest(method=method):
                vector = features(episode, method, 4, self.ecf, self.rff)
                self.assertEqual(len(vector), widths[method])
                self.assertTrue(all(math.isfinite(value) for value in vector))

    def test_ridge_fits_a_simple_mean_label(self):
        xs = [(float(x),) for x in (-1, 0, 1, 2, 3)]
        ys = [0.2 + 0.1*x[0] for x in xs]
        coefs = solve_ridge(xs, ys)
        self.assertAlmostEqual(coefs[0], 0.2, delta=0.08)
        self.assertGreater(coefs[1], 0)
        with self.assertRaises(ValueError):
            solve_ridge([(1.,), (2., 3.)], [0., 1.])

    def test_disjoint_seeds_and_cost_fields(self):
        case = run_case(n=12, d=4, k=4, regime="balanced",
                        train_seeds=(3101, 3102, 3103, 3104),
                        test_seeds=(9101, 9102))
        self.assertEqual(case["n"], 12)
        self.assertEqual(len(case["input_sha256"]), 64)
        self.assertEqual(set(case["models"]), set(METHODS))
        self.assertEqual(case["train_seeds"], [3101, 3102, 3103, 3104])
        for item in case["models"].values():
            self.assertEqual(set(item["holdout_mse"]), set(TASKS))
            self.assertGreaterEqual(item["encoding_p95_seconds"], 0)
            self.assertGreaterEqual(item["elapsed_process_cpu_seconds"], 0)
        with self.assertRaisesRegex(ValueError, "overlap"):
            run_case(n=12, d=4, k=4, regime="balanced",
                     train_seeds=(3101,), test_seeds=(3101,))

    def test_benchmark_is_reproducible_in_quality_not_wall_time(self):
        kwargs = dict(n=12, d=4, k=4, regime="rare",
                      train_seeds=(3101, 3102, 3103, 3104),
                      test_seeds=(9101, 9102))
        a, b = run_case(**kwargs), run_case(**kwargs)
        self.assertEqual(a["input_sha256"], b["input_sha256"])
        for method in METHODS:
            self.assertEqual(a["models"][method]["holdout_mse"],
                             b["models"][method]["holdout_mse"])
        self.assertEqual(a["target_group_mean_size"], 2)

    def test_invalid_case_and_frequency_arguments(self):
        with self.assertRaises(ValueError):
            make_episode(5, 4, 3101, "balanced")
        with self.assertRaises(ValueError):
            make_episode(20, 17, 3101, "balanced")
        with self.assertRaises(ValueError):
            frequencies(4, 0)
        with self.assertRaises(ValueError):
            features(make_episode(10, 4, 3101, "balanced"),
                     "impossible", 4, self.ecf, self.rff)

    def test_cli_json_smoke_cpu_only(self):
        script = ROOT / "benchmarks" / "w5_population_repr.py"
        result = subprocess.run(
            [sys.executable, str(script), "--agents", "12", "--dim", "4",
             "--frequencies", "4", "--train-episodes", "4",
             "--test-episodes", "2", "--regimes", "balanced"],
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "openworld.w5.population-representation.v0")
        self.assertEqual(report["cases"][0]["regime"], "balanced")
        self.assertEqual(report["cases"][0]["models"]["ecf"]["feature_width"], 8)

    def test_percentile_ceiling(self):
        self.assertEqual(_percentile([5., 1., 3., 2., 4.], 0.95), 5.)
        self.assertEqual(_percentile([5., 1., 3., 2., 4.], 0.5), 3.)


if __name__ == "__main__":
    unittest.main()
