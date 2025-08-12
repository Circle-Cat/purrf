load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "pubsub_puller",
    srcs = [
        "pubsub_puller.py",
    ],
    deps = [
        "//backend/common:asyncio_event_loop_manager",
        "//backend/common:constants",
        "//backend/common:google_client",
        "//backend/common:redis_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "pubsub_pull_manager",
    srcs = [
        "pubsub_pull_manager.py",
    ],
    deps = [
        "//backend/consumers:pubsub_puller",
    ],
)

py_library(
    name = "consumer_api",
    srcs = [
        "consumer_api.py",
    ],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/common:google_client",
        "//backend/consumers:gerrit_consumer",
        "//backend/consumers:google_chat_consumer",
        "//backend/consumers:microsoft_chat_consumer",
        "//backend/consumers:pubsub_pull_manager",
        "@pypi//flask",
    ],
)

py_library(
    name = "google_chat_consumer",
    srcs = [
        "google_chat_consumer.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:google_client",
        "//backend/common:logger",
        "//backend/consumers:pubsub_puller",
        "//backend/utils:google_chat_message_store",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_chat_consumer",
    srcs = [
        "microsoft_chat_consumer.py",
    ],
    deps = [
        "//backend/consumers:pubsub_puller",
        "//backend/utils:microsoft_chat_message_store",
    ],
)

py_library(
    name = "gerrit_consumer",
    srcs = [
        "gerrit_consumer.py",
    ],
    deps = [
        "//backend/common:logger",
        "//backend/common:redis_client",
        "//backend/consumers:pubsub_puller",
        "//backend/historical_data:gerrit_history_fetcher",
    ],
)

py_library(
    name = "pubsub_puller_factory",
    srcs = [
        "pubsub_puller_factory.py",
    ],
)
