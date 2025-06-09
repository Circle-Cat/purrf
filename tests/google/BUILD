load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_fetch_history_chat_message",
    srcs = ["test_fetch_history_chat_message.py"],
    deps = [
        "//google:fetch_history_chat_message",
    ],
)

py_test(
    name = "test_pubsub_publisher",
    srcs = ["test_pubsub_publisher.py"],
    deps = [
        "//google:pubsub_publisher",
    ],
)

py_test(
    name = "test_pubsub_subscriber_store",
    srcs = ["test_pubsub_subscriber_store.py"],
    deps = [
        "//google:pubsub_subscriber_store",
        "//src/utils:google_chat_message_store",
    ],
)
