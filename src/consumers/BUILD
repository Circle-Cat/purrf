load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "pubsub_puller",
    srcs = [
        "pubsub_puller.py",
    ],
    deps = [
        "//src/common:asyncio_event_loop_manager",
        "//src/common:constants",
        "//src/common:google_client",
        "//src/common:redis_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "pubsub_pull_manager",
    srcs = [
        "pubsub_pull_manager.py",
    ],
    deps = [
        "//src/consumers:pubsub_puller",
    ],
)

py_library(
    name = "consumer_api",
    srcs = [
        "consumer_api.py",
    ],
    deps = [
        "//src/common:api_response_wrapper",
        "//src/common:google_client",
        "//src/consumers:google_chat_consumer",
        "//src/consumers:gerrit_consumer",
        "//src/consumers:microsoft_chat_consumer",
        "//src/consumers:pubsub_pull_manager",
        "@pypi//flask",
    ],
)

py_library(
    name = "google_chat_consumer",
    srcs = [
        "google_chat_consumer.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:google_client",
        "//src/common:logger",
        "//src/consumers:pubsub_puller",
        "//src/utils:google_chat_message_store",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_chat_consumer",
    srcs = [
        "microsoft_chat_consumer.py",
    ],
    deps = [
        "//src/consumers:pubsub_puller",
        "//src/utils:microsoft_chat_message_store",
    ],
)

py_library(
    name = "gerrit_consumer",
    srcs = [
        "gerrit_consumer.py",
    ],
    deps = [
        "//src/common:logger",
        "//src/common:redis_client",
        "//src/consumers:pubsub_puller",
        "//src/historical_data:gerrit_history_fetcher",
    ],
)
