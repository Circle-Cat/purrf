import unittest

from pydantic import ValidationError

from backend.dto.job_dto import JobCreateDto


class TestJobCreateDtoCrossValidation(unittest.TestCase):
    def _form(self):
        return {
            "questions": [
                {
                    "id": "q3",
                    "type": "single_choice",
                    "label": "Fluent?",
                    "options": ["是", "否"],
                },
            ]
        }

    def test_answer_rule_questionid_must_exist(self):
        with self.assertRaises(ValidationError):
            JobCreateDto(
                title="T",
                formSchema=self._form(),
                screenRules={
                    "rules": [
                        {
                            "id": "r1",
                            "condition": {
                                "source": "answer",
                                "operator": "equals",
                                "questionId": "nope",
                                "value": "否",
                            },
                            "action": "reject",
                        },
                    ]
                },
            )

    def test_answer_rule_value_must_be_in_options(self):
        with self.assertRaises(ValidationError):
            JobCreateDto(
                title="T",
                formSchema=self._form(),
                screenRules={
                    "rules": [
                        {
                            "id": "r1",
                            "condition": {
                                "source": "answer",
                                "operator": "equals",
                                "questionId": "q3",
                                "value": "maybe",
                            },
                            "action": "reject",
                        },
                    ]
                },
            )

    def test_valid_answer_rule_accepted(self):
        dto = JobCreateDto(
            title="T",
            formSchema=self._form(),
            screenRules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "answer",
                            "operator": "equals",
                            "questionId": "q3",
                            "value": "否",
                        },
                        "action": "reject",
                    },
                ]
            },
            profileConfig={
                "education": "required",
                "workExperience": "off",
                "resume": "optional",
            },
        )
        self.assertEqual(dto.screen_rules.rules[0].action, "reject")

    def test_camel_case_aliases_accepted(self):
        dto = JobCreateDto(
            title="T",
            pipelineConfig={
                "ownerId": 5,
                "stages": [
                    {
                        "stage": "recruiter_screening",
                        "rounds": 1,
                        "referralSkippable": True,
                        "defaultAssigneeId": 7,
                    },
                ],
            },
        )
        self.assertEqual(dto.pipeline_config.owner_id, 5)
        self.assertTrue(dto.pipeline_config.stages[0].referral_skippable)


if __name__ == "__main__":
    unittest.main()
