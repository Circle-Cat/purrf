load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "microsoft_chat_producer_test",
    srcs = ["microsoft_chat_producer_test.py"],
    deps = [
        "//src/producers:microsoft_chat_producer",
    ],
)

py_test(
    name = "gerrit_producer_test",
    srcs = ["gerrit_producer_test.py"],
    deps = [
        "//src/producers:gerrit_producer",
    ],
)

py_test(
    name = "microsoft_lifecycle_notification_handler_test",
    srcs = ["microsoft_lifecycle_notification_handler_test.py"],
    deps = [
        "//src/producers:microsoft_lifecycle_notification_handler",
    ],
)
