load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "redis_client_factory",
    srcs = [
        "constants.py",
        "redis_client_factory.py",
    ],
    deps = [
        "//tools/log",
        "@pypi//redis",
    ],
)

py_library(
    name = "redis_utils",
    srcs = [
        "constants.py",
        "redis_utils.py",
    ],
    deps = [
        ":redis_client_factory",
        "//tools/log",
    ],
)
