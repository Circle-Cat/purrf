load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "google_chat_consumer_test",
    srcs = ["google_chat_consumer_test.py"],
    deps = [
        "//backend/consumers:google_chat_consumer",
    ],
)

py_test(
    name = "pubsub_puller_test",
    srcs = ["pubsub_puller_test.py"],
    deps = [
        "//backend/consumers:pubsub_puller",
    ],
)

py_test(
    name = "pubsub_pull_manager_test",
    srcs = ["pubsub_pull_manager_test.py"],
    deps = [
        "//backend/consumers:pubsub_pull_manager",
    ],
)

py_test(
    name = "microsoft_chat_consumer_test",
    srcs = ["microsoft_chat_consumer_test.py"],
    deps = [
        "//backend/consumers:microsoft_chat_consumer",
    ],
)

py_test(
    name = "consumer_api_test",
    srcs = ["consumer_api_test.py"],
    deps = [
        "//backend/consumers:consumer_api",
    ],
)

py_test(
    name = "gerrit_consumer_test",
    srcs = ["gerrit_consumer_test.py"],
    deps = [
        "//backend/consumers:gerrit_consumer",
    ],
)

py_test(
    name = "pubsub_puller_factory_test",
    srcs = ["pubsub_puller_factory_test.py"],
    deps = [
        "//backend/consumers:pubsub_puller_factory",
    ],
)
