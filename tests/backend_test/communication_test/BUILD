load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "email_conversation_service_test",
    srcs = ["email_conversation_service_test.py"],
    deps = [
        "//backend/common:communication_enums",
        "//backend/communication",
    ],
)

py_test(
    name = "email_templates_test",
    srcs = ["email_templates_test.py"],
    deps = [
        "//backend/communication",
    ],
)

py_test(
    name = "meeting_scheduling_service_test",
    srcs = ["meeting_scheduling_service_test.py"],
    deps = [
        "//backend/communication",
    ],
)
