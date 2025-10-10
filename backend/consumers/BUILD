load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "pubsub_puller",
    srcs = [
        "pubsub_puller.py",
    ],
    deps = [
        "//backend/common:constants",
        "@pypi//google_api_python_client",
    ],
)

py_library(
    name = "pubsub_pull_manager",
    srcs = [
        "pubsub_pull_manager.py",
    ],
    deps = [
        ":pubsub_puller",
    ],
)

py_library(
    name = "consumer_controller",
    srcs = [
        "consumer_controller.py",
    ],
    deps = [
        ":pubsub_pull_manager",
        "//backend/common:api_response_wrapper",
        "@pypi//flask",
    ],
)

py_library(
    name = "google_chat_processor_service",
    srcs = [
        "google_chat_processor_service.py",
    ],
    deps = [
        ":pubsub_puller",
        "//backend/common:constants",
        "//backend/common:google_client",
        "//backend/common:logger",
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
