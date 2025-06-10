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
