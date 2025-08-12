load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "microsoft_chat_producer",
    srcs = [
        "microsoft_chat_producer/main.py",
    ],
    deps = [
        "@pypi//functions_framework",
        "@pypi//google_cloud_pubsub",
        "@pypi//redis",
    ],
)

py_library(
    name = "gerrit_producer",
    srcs = [
        "gerrit_producer/main.py",
    ],
    deps = [
        "@pypi//functions_framework",
        "@pypi//google_cloud_pubsub",
    ],
)

py_library(
    name = "microsoft_lifecycle_notification_handler",
    srcs = [
        "microsoft_lifecycle_notification_handler/main.py",
    ],
    deps = [
        "@pypi//azure_identity",
        "@pypi//functions_framework",
        "@pypi//jsonschema",
        "@pypi//msgraph_sdk",
        "@pypi//redis",
    ],
)
