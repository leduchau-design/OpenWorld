"""Unit tests for the Unified Interactive Playground & AI Agent Sandbox."""
from __future__ import annotations

import unittest
from examples.interactive_playground import AIBrain, PlaygroundWorld


class TestInteractivePlayground(unittest.TestCase):
    def setUp(self) -> None:
        self.pw = PlaygroundWorld()

    def tearDown(self) -> None:
        self.pw.close()

    def test_initial_world_state(self) -> None:
        self.assertEqual(self.pw.current_world.tick, 0)
        self.assertIn("alice", self.pw.agents_dict)
        self.assertIn("bob", self.pw.agents_dict)
        self.assertTrue(self.pw.verify_chain())

    def test_add_agent_and_connect(self) -> None:
        self.pw.add_agent("charlie", balance=10, region="mid", owner="owner1")
        self.assertIn("charlie", self.pw.agents_dict)
        self.pw.connect("alice", "charlie")
        obs = self.pw.observe("alice")
        self.assertIn("charlie", obs.neighbors)
        self.assertTrue(self.pw.verify_chain())

    def test_transfer_and_tick(self) -> None:
        # Alice transfers 1 to Bob
        req_id = self.pw.queue_action("alice", "bob", "transfer", 1)
        self.assertTrue(req_id.startswith("cmd-0-alice"))
        step = self.pw.tick()
        self.assertEqual(self.pw.current_world.tick, 1)
        self.assertIn(req_id, step.accepted)
        self.assertEqual(self.pw.agents_dict["alice"].resources, 4)
        self.assertEqual(self.pw.agents_dict["bob"].resources, 6)
        self.assertTrue(self.pw.verify_chain())

        # Check memory recorded
        pred, est = self.pw.get_prediction("alice")
        self.assertGreater(pred, 0.0)

    def test_signal_and_inbox(self) -> None:
        req_id = self.pw.queue_action("bob", "alice", "signal")
        step = self.pw.tick()
        self.assertIn(req_id, step.accepted)
        obs_alice = self.pw.observe("alice")
        # Alice should see bob's signal in inbox
        self.assertTrue(any(sender == "bob" for sender, _ in obs_alice.inbox))
        self.assertTrue(self.pw.verify_chain())

    def test_weather_update(self) -> None:
        self.pw.set_weather("north", "rain")
        step = self.pw.tick()
        obs_alice = self.pw.observe("alice")
        self.assertEqual(obs_alice.weather, "rain")
        self.assertTrue(self.pw.verify_chain())

    def test_ai_heuristic_think_and_act(self) -> None:
        decision = self.pw.ask_agent("alice", "send a greeting signal to bob")
        self.assertIn("thought", decision)
        self.assertIn("message", decision)
        self.assertIn(decision.get("action"), ("signal", "transfer", "hold"))

        dec2, step = self.pw.act_with_ai("alice", "say hello to bob with signal")
        self.assertEqual(self.pw.current_world.tick, 1)
        self.assertTrue(self.pw.verify_chain())

    def test_multi_tick_replay_verification(self) -> None:
        for _ in range(5):
            self.pw.act_with_ai("alice", "cooperate with neighbor")
        self.assertEqual(self.pw.current_world.tick, 5)
        self.assertTrue(self.pw.verify_chain())


if __name__ == "__main__":
    unittest.main()
