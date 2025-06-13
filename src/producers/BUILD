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
