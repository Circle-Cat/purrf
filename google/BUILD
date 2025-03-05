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
    ],
)

py_library(
    name = "chat_utils",
    srcs = [
        "chat_utils.py",
        "constants.py",
    ],
    deps = [
        "//tools/log",
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
        "//redis_dal:redis_utils",
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
        "//tools/global_handle_exception:exception_handler",
        "//tools/log",
        "@pypi//flask",
    ],
)
