"""Research-only institution charter review: non-escalation and no side effects."""
import sys
from pathlib import Path
from dataclasses import FrozenInstanceError, replace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openworld_superkernel.institution_proposals import (
    CharterProposal, review_charter,
)
from openworld_superkernel.population_links import (
    Population, PopulationLink, PopulationRouter,
)
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_guard import GuardedWorldGateway
from openworld_superkernel.world_fixture import Agent, TickInput, advance, create_world


class InstitutionCharterTests(unittest.TestCase):
    def setUp(self):
        self.world = create_world((
            Agent("a", "owner-a", "north", 4), Agent("b", "owner-a", "north", 4),
            Agent("c", "owner-a", "south", 3), Agent("d", "owner-a", "south", 2),
        ), (("a", "b"), ("b", "c"), ("c", "d")), seed=101)
        authority = CapabilityAuthority(
            b"research-only-charter-fixture-key-not-for-any-deployment",
            issuer="test", audience="world",
        )
        gateway = GuardedWorldGateway(
            authority, authenticated_principal=lambda: "toy-host")
        self.router = PopulationRouter(gateway, (
            Population("A", ("a", "b")), Population("B", ("c", "d")),
        ), (
            PopulationLink("A", "B", ("signal", "transfer"),
                           max_transfer=3, max_actions_per_tick=2),
            PopulationLink("B", "A", ("signal",),
                           max_transfer=0, max_actions_per_tick=1),
        ))
        self.draft = CharterProposal(
            "charter-01", "owner-a", ("b", "c"),
            "Pilot bounded cooperation with owner review",
            (PopulationLink("A", "B", ("transfer",), 2, 1),),
            1, 0, 3,
        )

    def review(self, proposal=None, world=None, trusted_owner="owner-a"):
        return review_charter(world or self.world, self.router,
                              proposal or self.draft, trusted_owner=trusted_owner)

    def test_eligible_is_only_a_nonbinding_recommendation(self):
        before = self.world.fingerprint()
        old_links = dict(self.router.links)
        review = self.review()
        self.assertTrue(review.eligible)
        self.assertEqual(review.verdict, "ELIGIBLE_FOR_OWNER_REVIEW")
        self.assertEqual(review.reasons, ())
        self.assertTrue(review.proposal_digest.startswith("sha256:"))
        self.assertEqual(before, self.world.fingerprint())
        self.assertEqual(old_links, self.router.links)
        self.assertFalse(hasattr(review, "capability"))
        self.assertFalse(hasattr(review, "approval_token"))

    def test_draft_is_immutable_and_content_addressed(self):
        with self.assertRaises(FrozenInstanceError):
            self.draft.proposed_owner = "owner-b"
        alternative = replace(self.draft, purpose="Different purpose")
        self.assertNotEqual(self.review().proposal_digest,
                            self.review(alternative).proposal_digest)

    def test_forged_owner_rejected(self):
        review = self.review(trusted_owner="not-the-owner")
        self.assertFalse(review.eligible)
        self.assertIn("owner_claim_mismatch", review.reasons)

    def test_cross_owner_member_rejected(self):
        other = create_world((
            Agent("a", "owner-a", "north", 4), Agent("b", "owner-a", "north", 4),
            Agent("c", "owner-b", "south", 3), Agent("d", "owner-b", "south", 2),
        ), (("a", "b"), ("b", "c"), ("c", "d")), seed=101)
        check = self.review(world=other)
        self.assertFalse(check.eligible)
        self.assertIn("cross_owner_member", check.reasons)

    def test_new_link_denied(self):
        draft = replace(self.draft, links=(
            PopulationLink("B", "A", ("transfer",), 1, 1),
        ))
        check = self.review(draft)
        self.assertFalse(check.eligible)
        self.assertIn("action_scope_escalation", check.reasons)

    def test_more_actions_or_transfer_exceeds_existing_limits(self):
        draft = replace(self.draft, links=(
            PopulationLink("A", "B", ("transfer",), 4, 3),
        ), max_total_actions_per_tick=4)
        self.assertIn("quota_escalation", self.review(draft).reasons)

    def test_more_total_actions_than_charter_budget(self):
        draft = replace(self.draft, links=(
            PopulationLink("A", "B", ("transfer",), 2, 2),
            PopulationLink("B", "A", ("signal",), 0, 1),
        ), max_total_actions_per_tick=2)
        self.assertIn("aggregate_quota_exceeded", self.review(draft).reasons)

    def test_unrepresented_group_denied(self):
        draft = replace(self.draft, members=("a", "b"))
        self.assertIn("unrepresented_group", self.review(draft).reasons)

    def test_unknown_member_denied(self):
        draft = replace(self.draft, members=("b", "ghost"))
        self.assertIn("unknown_member", self.review(draft).reasons)

    def test_stale_expected_tick_rejected(self):
        after = advance(self.world, TickInput(0, (), ())).world
        self.assertIn("stale_or_expired_charter", self.review(world=after).reasons)

    def test_roster_drift_rejected(self):
        other = create_world((
            Agent("a", "owner-a", "north", 4), Agent("b", "owner-a", "north", 4),
            Agent("c", "owner-a", "south", 3),
        ), (("a", "b"), ("b", "c")), seed=101)
        self.assertIn("roster_drift", self.review(world=other).reasons)

    def test_invalid_draft_refused(self):
        for bad in (
            replace(self.draft, members=("b", "b")),
            replace(self.draft, max_total_actions_per_tick=0),
            replace(self.draft, expires_at_tick=0),
            replace(self.draft, links=()),
            replace(self.draft, purpose=""),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.review(bad)

    def test_missing_trusted_owner_refused(self):
        with self.assertRaises(PermissionError):
            self.review(trusted_owner="")


if __name__ == "__main__":
    unittest.main()
