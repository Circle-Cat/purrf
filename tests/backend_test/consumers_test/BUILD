load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "google_chat_processor_service_test",
    srcs = ["google_chat_processor_service_test.py"],
    deps = [
        "//backend/consumers:google_chat_processor_service",
    ],
)

py_test(
    name = "pubsub_puller_test",
    srcs = ["pubsub_puller_test.py"],
    deps = [
        "//backend/common:asyncio_event_loop_manager",
        "//backend/consumers:pubsub_puller",
    ],
)

py_test(
    name = "pubsub_pull_manager_test",
    srcs = ["pubsub_pull_manager_test.py"],
    deps = [
        "//backend/consumers:pubsub_pull_manager",
        "//backend/consumers:pubsub_puller",
    ],
)

py_test(
    name = "microsoft_message_processor_service_test",
    srcs = ["microsoft_message_processor_service_test.py"],
    deps = [
        "//backend/consumers:microsoft_message_processor_service",
    ],
)

py_test(
    name = "consumer_controller_test",
    srcs = ["consumer_controller_test.py"],
    deps = [
        "//backend/consumers:consumer_controller",
    ],
)

py_test(
    name = "gerrit_processor_service_test",
    srcs = ["gerrit_processor_service_test.py"],
    deps = [
        "//backend/consumers:gerrit_processor_service",
    ],
)

py_test(
    name = "pubsub_puller_factory_test",
    srcs = ["pubsub_puller_factory_test.py"],
    deps = [
        "//backend/consumers:pubsub_puller_factory",
    ],
)
