load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "environment_constants",
    srcs = ["environment_constants.py"],
)

py_library(
    name = "logger",
    srcs = ["logger.py"],
    deps = ["//src/common:environment_constants"],
)

py_library(
    name = "constants",
    srcs = ["constants.py"],
)

py_library(
    name = "google_client",
    srcs = [
        "google_client.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:logger",
        "@pypi//google_api_python_client",
        "@pypi//google_auth_oauthlib",
        "@pypi//google_cloud_pubsub",
        "@pypi//grpcio",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "redis_client",
    srcs = ["redis_client.py"],
    deps = [
        "//src/common:constants",
        "//src/common:logger",
        "@pypi//redis",
        "@pypi//tenacity",
    ],
)
