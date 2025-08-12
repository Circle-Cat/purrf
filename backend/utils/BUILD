load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "google_chat_message_store",
    srcs = [
        "google_chat_message_store.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:redis_client",
    ],
)

py_library(
    name = "google_chat_utils",
    srcs = [
        "google_chat_utils.py",
    ],
    deps = [
        "//backend/common:google_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_chat_message_store",
    srcs = [
        "microsoft_chat_message_store.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:microsoft_client",
        "//backend/common:redis_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "date_time_util",
    srcs = [
        "date_time_util.py",
    ],
    deps = [
        "//backend/common:constants",
        "@pypi//python_dateutil",
    ],
)

py_library(
    name = "retry_utils",
    srcs = [
        "retry_utils.py",
    ],
    deps = [
        "@pypi//tenacity",
    ],
)
