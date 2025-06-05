load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "authentication_utils",
    srcs = [
        "authentication_utils.py",
        "constants.py",
    ],
    deps = [
        "//tools/log",
        "@pypi//google_api_python_client",
        "@pypi//google_auth_oauthlib",
        "@pypi//google_cloud_pubsub",
        "@pypi//grpcio",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "chat_utils",
    srcs = [
        "authentication_utils.py",
        "chat_utils.py",
        "constants.py",
    ],
    deps = [
        "//google:authentication_utils",
        "//tools/log",
        "@pypi//google_api_python_client",
        "@pypi//google_cloud_pubsub",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "fetch_history_chat_message",
    srcs = [
        "constants.py",
        "fetch_history_chat_message.py",
    ],
    deps = [
        ":authentication_utils",
        ":chat_utils",
        "//src/historical_data:google_chat_history_fetcher",
        "//src/utils:google_chat_message_store",
        "//src/utils:google_chat_utils",
        "//tools/log",
    ],
)

py_library(
    name = "google_api",
    srcs = ["google_api.py"],
    deps = [
        "fetch_history_chat_message",
        ":authentication_utils",
        ":chat_utils",
        ":pubsub_publisher",
        ":pubsub_subscriber_store",
        "//tools/global_handle_exception:exception_handler",
        "//tools/log",
        "@pypi//flask",
    ],
)

py_library(
    name = "pubsub_publisher",
    srcs = [
        "pubsub_publisher.py",
    ],
    deps = [
        "//google:authentication_utils",
        "//tools/log",
        "@pypi//google_api_python_client",
        "@pypi//google_cloud_pubsub",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "pubsub_subscriber_store",
    srcs = [
        "constants.py",
        "pubsub_subscriber_store.py",
    ],
    deps = [
        "//google:authentication_utils",
        "//src/utils:google_chat_message_store",
        "//tools/log",
        "@pypi//google_api_python_client",
        "@pypi//google_auth_oauthlib",
        "@pypi//google_cloud_pubsub",
    ],
)
