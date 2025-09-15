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
    name = "consumer_controller",
    srcs = [
        "consumer_controller.py",
    ],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/consumers:pubsub_pull_manager",
        "@pypi//flask",
    ],
)

py_library(
    name = "google_chat_processor_service",
    srcs = [
        "google_chat_processor_service.py",
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
    name = "microsoft_message_processor_service",
    srcs = [
        "microsoft_message_processor_service.py",
    ],
)

py_library(
    name = "gerrit_processor_service",
    srcs = [
        "gerrit_processor_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "pubsub_puller_factory",
    srcs = [
        "pubsub_puller_factory.py",
    ],
)
