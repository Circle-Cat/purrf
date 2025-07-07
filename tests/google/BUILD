load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_pubsub_subscriber_store",
    srcs = ["test_pubsub_subscriber_store.py"],
    deps = [
        "//google:pubsub_subscriber_store",
        "//src/utils:google_chat_message_store",
    ],
)
