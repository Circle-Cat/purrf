load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "pubsub_puller",
    srcs = [
        "pubsub_puller.py",
    ],
    deps = [
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
        "//src/consumers:pubsub_pull_manager",
        "@pypi//flask",
    ],
)
