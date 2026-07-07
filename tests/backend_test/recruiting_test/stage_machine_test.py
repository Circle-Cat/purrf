import unittest
from backend.common.recruiting_enums import ApplicationStage
from backend.recruiting.stage_machine import (
    PIPELINE_ORDER,
    SUB_STATUS_SETS,
    configured_stages,
    first_stage,
    advance_target,
    validate_transition,
    validate_sub_status,
    rounds_for_stage,
)


class TestConfiguredStages(unittest.TestCase):
    def test_none_config_yields_empty(self):
        self.assertEqual(configured_stages(None), [])

    def test_missing_stages_key_yields_empty(self):
        self.assertEqual(configured_stages({"ownerIds": []}), [])

    def test_subset_is_sorted_by_global_pipeline_order(self):
        cfg = {"stages": [{"stage": "tech"}, {"stage": "recruiter_screening"}]}
        self.assertEqual(
            configured_stages(cfg),
            [ApplicationStage.RECRUITER_SCREENING, ApplicationStage.TECH],
        )

    def test_non_pipeline_entries_are_filtered_out(self):
        cfg = {"stages": [{"stage": "applied"}, {"stage": "behavioral"}]}
        self.assertEqual(configured_stages(cfg), [ApplicationStage.BEHAVIORAL])


class TestFirstStage(unittest.TestCase):
    def test_falls_back_to_recruiter_screening_when_unconfigured(self):
        self.assertEqual(first_stage(None), ApplicationStage.RECRUITER_SCREENING)

    def test_returns_first_configured_stage(self):
        cfg = {"stages": [{"stage": "tech"}, {"stage": "board_review"}]}
        self.assertEqual(first_stage(cfg), ApplicationStage.TECH)


class TestAdvanceTarget(unittest.TestCase):
    def test_advances_mid_pipeline(self):
        cfg = {"stages": [{"stage": "recruiter_screening"}, {"stage": "tech"}]}
        self.assertEqual(
            advance_target(cfg, ApplicationStage.RECRUITER_SCREENING),
            ApplicationStage.TECH,
        )

    def test_advances_from_last_configured_to_offer(self):
        cfg = {"stages": [{"stage": "recruiter_screening"}, {"stage": "tech"}]}
        self.assertEqual(
            advance_target(cfg, ApplicationStage.TECH), ApplicationStage.OFFER
        )

    def test_advances_from_offer_to_hired(self):
        cfg = {"stages": [{"stage": "recruiter_screening"}, {"stage": "tech"}]}
        self.assertEqual(
            advance_target(cfg, ApplicationStage.OFFER), ApplicationStage.HIRED
        )

    def test_advances_to_offer_even_for_a_single_stage_pipeline(self):
        cfg = {"stages": [{"stage": "recruiter_screening"}]}
        self.assertEqual(
            advance_target(cfg, ApplicationStage.RECRUITER_SCREENING),
            ApplicationStage.OFFER,
        )

    def test_returns_none_from_terminal_or_unconfigured_current(self):
        cfg = {"stages": [{"stage": "recruiter_screening"}]}
        self.assertIsNone(advance_target(cfg, ApplicationStage.REJECTED))
        self.assertIsNone(advance_target(cfg, ApplicationStage.HIRED))
        self.assertIsNone(advance_target(cfg, ApplicationStage.TECH))


class TestValidateTransition(unittest.TestCase):
    def setUp(self):
        self.cfg = {"stages": [{"stage": "recruiter_screening"}, {"stage": "tech"}]}

    def test_accepts_advance_to_next_configured_stage(self):
        validate_transition(
            self.cfg, ApplicationStage.RECRUITER_SCREENING, ApplicationStage.TECH
        )

    def test_accepts_advance_from_last_configured_to_offer(self):
        validate_transition(self.cfg, ApplicationStage.TECH, ApplicationStage.OFFER)

    def test_accepts_advance_from_offer_to_hired(self):
        validate_transition(self.cfg, ApplicationStage.OFFER, ApplicationStage.HIRED)

    def test_accepts_reject_from_offer(self):
        validate_transition(self.cfg, ApplicationStage.OFFER, ApplicationStage.REJECTED)

    def test_accepts_reject_from_any_configured_pipeline_stage(self):
        validate_transition(
            self.cfg, ApplicationStage.RECRUITER_SCREENING, ApplicationStage.REJECTED
        )
        validate_transition(self.cfg, ApplicationStage.TECH, ApplicationStage.REJECTED)

    def test_rejects_skip_ahead(self):
        with self.assertRaises(ValueError):
            validate_transition(
                self.cfg, ApplicationStage.RECRUITER_SCREENING, ApplicationStage.HIRED
            )

    def test_rejects_backward_move(self):
        with self.assertRaises(ValueError):
            validate_transition(
                self.cfg, ApplicationStage.TECH, ApplicationStage.RECRUITER_SCREENING
            )

    def test_rejects_move_from_terminal_stage(self):
        with self.assertRaises(ValueError):
            validate_transition(
                self.cfg, ApplicationStage.HIRED, ApplicationStage.REJECTED
            )


class TestValidateSubStatus(unittest.TestCase):
    def test_valid_values_per_stage(self):
        validate_sub_status(ApplicationStage.RECRUITER_SCREENING, "in_progress")
        validate_sub_status(ApplicationStage.BOARD_REVIEW, "evaluated")
        validate_sub_status(ApplicationStage.BEHAVIORAL, "scheduling")
        validate_sub_status(ApplicationStage.TECH, "scheduled")

    def test_invalid_value_for_stage_raises(self):
        with self.assertRaises(ValueError):
            validate_sub_status(ApplicationStage.BEHAVIORAL, "evaluated_wrong")

    def test_offer_has_no_sub_status_set_and_raises(self):
        with self.assertRaises(ValueError):
            validate_sub_status(ApplicationStage.OFFER, "pending")

    def test_terminal_stage_has_no_set_and_raises(self):
        with self.assertRaises(ValueError):
            validate_sub_status(ApplicationStage.REJECTED, "pending")

    def test_sub_status_sets_matrix_matches_spec(self):
        self.assertEqual(
            SUB_STATUS_SETS[ApplicationStage.RECRUITER_SCREENING],
            ("pending", "in_progress", "evaluated"),
        )
        self.assertEqual(
            SUB_STATUS_SETS[ApplicationStage.BOARD_REVIEW],
            ("pending", "in_progress", "evaluated"),
        )
        self.assertEqual(
            SUB_STATUS_SETS[ApplicationStage.BEHAVIORAL],
            ("pending", "scheduling", "scheduled", "evaluated"),
        )
        self.assertEqual(
            SUB_STATUS_SETS[ApplicationStage.TECH],
            ("pending", "scheduling", "scheduled", "evaluated"),
        )
        self.assertNotIn(ApplicationStage.OFFER, SUB_STATUS_SETS)


class TestPipelineOrder(unittest.TestCase):
    def test_pipeline_order_matches_spec(self):
        self.assertEqual(
            PIPELINE_ORDER,
            [
                ApplicationStage.RECRUITER_SCREENING,
                ApplicationStage.BEHAVIORAL,
                ApplicationStage.TECH,
                ApplicationStage.BOARD_REVIEW,
            ],
        )

    def test_offer_is_not_a_configurable_stage(self):
        self.assertNotIn(ApplicationStage.OFFER, PIPELINE_ORDER)


class TestRoundsForStage(unittest.TestCase):
    def test_returns_configured_rounds_for_the_stage(self):
        cfg = {"stages": [{"stage": "tech", "rounds": 3}]}
        self.assertEqual(rounds_for_stage(cfg, ApplicationStage.TECH), 3)

    def test_defaults_to_one_when_stage_is_not_configured(self):
        cfg = {"stages": [{"stage": "tech", "rounds": 3}]}
        self.assertEqual(rounds_for_stage(cfg, ApplicationStage.RECRUITER_SCREENING), 1)

    def test_defaults_to_one_for_falsy_pipeline_config(self):
        self.assertEqual(rounds_for_stage(None, ApplicationStage.TECH), 1)
        self.assertEqual(rounds_for_stage({}, ApplicationStage.TECH), 1)

    def test_defaults_to_one_when_entry_omits_rounds(self):
        cfg = {"stages": [{"stage": "tech"}]}
        self.assertEqual(rounds_for_stage(cfg, ApplicationStage.TECH), 1)

    def test_defaults_to_one_for_a_non_positive_rounds_value(self):
        cfg = {"stages": [{"stage": "tech", "rounds": 0}]}
        self.assertEqual(rounds_for_stage(cfg, ApplicationStage.TECH), 1)


if __name__ == "__main__":
    unittest.main()
