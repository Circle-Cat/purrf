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
    name = "google_api",
    srcs = ["google_api.py"],
    deps = [
        ":authentication_utils",
        ":pubsub_subscriber_store",
        "//src/utils:google_chat_utils",
        "//tools/global_handle_exception:exception_handler",
        "//tools/log",
        "@pypi//flask",
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
        "//src/consumers:google_chat_consumer",
        "//src/utils:google_chat_message_store",
        "//tools/log",
        "@pypi//google_api_python_client",
        "@pypi//google_auth_oauthlib",
        "@pypi//google_cloud_pubsub",
    ],
)
