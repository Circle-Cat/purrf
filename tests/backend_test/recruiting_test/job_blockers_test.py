import unittest
from types import SimpleNamespace

from backend.recruiting.job_blockers import (
    NO_RECRUITER,
    NO_STAGE,
    effective_pipeline_config,
    submit_blockers,
)


def _job(pipeline_config=None, pending_payload=None):
    """A stand-in JobEntity carrying only the two fields the rule reads."""
    return SimpleNamespace(
        pipeline_config=pipeline_config, pending_payload=pending_payload
    )


class SubmitBlockersTest(unittest.TestCase):
    """What stops a posting being submitted, as a list rather than a raise."""

    def test_empty_config_blocks_on_both_counts(self):
        self.assertEqual(submit_blockers(_job()), [NO_STAGE, NO_RECRUITER])

    def test_reports_both_blockers_not_just_the_first(self):
        self.assertEqual(len(submit_blockers(_job({}))), 2)

    def test_stage_without_recruiter_blocks_on_recruiter_only(self):
        job = _job({"stages": [{"key": "tech"}]})
        self.assertEqual(submit_blockers(job), [NO_RECRUITER])

    def test_recruiter_without_stage_blocks_on_stage_only(self):
        job = _job({"ownerIds": [7]})
        self.assertEqual(submit_blockers(job), [NO_STAGE])

    def test_complete_config_has_no_blockers(self):
        job = _job({"stages": [{"key": "tech"}], "ownerIds": [7]})
        self.assertEqual(submit_blockers(job), [])

    def test_legacy_single_owner_shape_counts_as_a_recruiter(self):
        job = _job({"stages": [{"key": "tech"}], "ownerId": 7})
        self.assertEqual(submit_blockers(job), [])

    def test_staged_edit_is_judged_not_the_live_config(self):
        job = _job(
            pipeline_config={"stages": [{"key": "tech"}], "ownerIds": [7]},
            pending_payload={"pipelineConfig": {"ownerIds": [7]}},
        )
        self.assertEqual(submit_blockers(job), [NO_STAGE])

    def test_a_staged_edit_with_no_pipeline_key_is_an_empty_config(self):
        job = _job(
            pipeline_config={"stages": [{"key": "tech"}], "ownerIds": [7]},
            pending_payload={},
        )
        self.assertEqual(len(submit_blockers(job)), 2)


class EffectivePipelineConfigTest(unittest.TestCase):
    """Which of the two stored configs a submission is judged on."""

    def test_no_staged_edit_uses_the_live_config(self):
        live = {"stages": [{"key": "tech"}]}
        self.assertEqual(effective_pipeline_config(_job(live)), live)

    def test_a_staged_edit_wins_over_the_live_config(self):
        staged = {"stages": [{"key": "behavioral"}]}
        job = _job({"stages": [{"key": "tech"}]}, {"pipelineConfig": staged})
        self.assertEqual(effective_pipeline_config(job), staged)

    def test_a_null_staged_pipeline_is_an_empty_config_not_the_live_one(self):
        job = _job({"stages": [{"key": "tech"}]}, {"pipelineConfig": None})
        self.assertEqual(effective_pipeline_config(job), {})

    def test_missing_config_is_an_empty_dict(self):
        self.assertEqual(effective_pipeline_config(_job()), {})


if __name__ == "__main__":
    unittest.main()
