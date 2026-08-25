load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "backfill_activity_application_gate_test",
    srcs = ["backfill_activity_application_gate_test.py"],
    deps = ["//backend/backfill:backfill_activity_application_gate_lib"],
)

py_test(
    name = "export_mentorship_records_test",
    srcs = ["export_mentorship_records_test.py"],
    deps = ["//backend/backfill:export_mentorship_records_lib"],
)

py_test(
    name = "export_ineligible_mentees_test",
    srcs = ["export_ineligible_mentees_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/backfill:export_mentorship_records_lib",
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)
