load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "constants",
    srcs = ["constants.py"],
)

py_library(
    name = "redis_api",
    srcs = ["redis_api.py"],
    deps = [
        "//redis_dal:redis_query_utils",
        "//tools/global_handle_exception:exception_handler",
        "@pypi//flask",
    ],
)

py_library(
    name = "redis_client_factory",
    srcs = ["redis_client_factory.py"],
    deps = [
        "//redis_dal:constants",
        "//tools/log",
        "@pypi//redis",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "redis_query_utils",
    srcs = ["redis_query_utils.py"],
    deps = [
        ":constants",
        ":redis_client_factory",
        "//google:chat_utils",
        "//src/utils:google_chat_utils",
        "@pypi//python_dateutil",
        "@pypi//redis",
    ],
)
