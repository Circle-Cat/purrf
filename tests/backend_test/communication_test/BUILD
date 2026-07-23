load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "email_conversation_service_test",
    srcs = ["email_conversation_service_test.py"],
    deps = [
        "//backend/common:communication_enums",
        "//backend/communication",
    ],
)
