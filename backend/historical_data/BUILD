load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "constants",
    srcs = ["constants.py"],
)

py_library(
    name = "google_calendar_sync_service",
    srcs = [
        "google_calendar_sync_service.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/dto",
    ],
)

py_library(
    name = "microsoft_member_sync_service",
    srcs = [
        "microsoft_member_sync_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "historical_controller",
    srcs = ["historical_controller.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:user_role",
        "//backend/utils:date_time_util",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)

py_library(
    name = "google_chat_history_sync_service",
    srcs = [
        "google_chat_history_sync_service.py",
    ],
)

py_library(
    name = "gerrit_sync_service",
    srcs = [
        "gerrit_sync_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "microsoft_chat_history_sync_service",
    srcs = [
        "microsoft_chat_history_sync_service.py",
    ],
)

py_library(
    name = "jira_history_sync_service",
    srcs = [
        "jira_history_sync_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)
