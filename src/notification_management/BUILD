load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "microsoft_chat_watcher",
    srcs = [
        "microsoft_chat_watcher.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:microsoft_client",
        "//src/common:redis_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "notification_api",
    srcs = [
        "notification_api.py",
    ],
    deps = [
        "//src/common:api_response_wrapper",
        "//src/common:constants",
        "//src/notification_management:gerrit_watcher",
        "//src/notification_management:google_chat_watcher",
        "//src/notification_management:microsoft_chat_watcher",
        "@pypi//flask",
    ],
)

py_library(
    name = "gerrit_watcher",
    srcs = [
        "gerrit_watcher.py",
    ],
    deps = [
        "//src/common:gerrit_client",
    ],
)

py_library(
    name = "google_chat_watcher",
    srcs = [
        "google_chat_watcher.py",
    ],
    deps = [
        "//src/common:google_client",
    ],
)
