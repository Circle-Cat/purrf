load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "microsoft_chat_watcher",
    srcs = [
        "microsoft_chat_watcher.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:microsoft_client",
        "//backend/common:redis_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "notification_api",
    srcs = [
        "notification_api.py",
    ],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/common:constants",
        "//backend/notification_management:gerrit_watcher",
        "//backend/notification_management:google_chat_watcher",
        "//backend/notification_management:microsoft_chat_watcher",
        "@pypi//flask",
    ],
)

py_library(
    name = "gerrit_watcher",
    srcs = [
        "gerrit_watcher.py",
    ],
    deps = [
        "//backend/common:gerrit_client",
    ],
)

py_library(
    name = "google_chat_watcher",
    srcs = [
        "google_chat_watcher.py",
    ],
    deps = [
        "//backend/common:google_client",
    ],
)
