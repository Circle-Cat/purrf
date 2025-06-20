load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "google_chat_message_store",
    srcs = [
        "google_chat_message_store.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:redis_client",
    ],
)

py_library(
    name = "google_chat_utils",
    srcs = [
        "google_chat_utils.py",
    ],
    deps = [
        "//src/common:google_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_chat_message_store",
    srcs = [
        "microsoft_chat_message_store.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:microsoft_client",
        "//src/common:redis_client",
        "@pypi//tenacity",
    ],
)
