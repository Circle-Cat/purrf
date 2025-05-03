load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_chat_utils",
    srcs = ["test_chat_utils.py"],
    deps = [
        "//google:authentication_utils",
        "//google:chat_utils",
    ],
)

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
        "//google:chat_utils",
        "//google:pubsub_subscriber_store",
        "//redis_dal:redis_utils",
    ],
)
