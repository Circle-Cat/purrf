load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "constants",
    srcs = ["constants.py"],
)

py_library(
    name = "google_calendar_history_fetcher",
    srcs = [
        "google_calendar_history_fetcher.py",
    ],
    deps = [
        "//backend/common:google_client",
        "//backend/common:logger",
        "//backend/common:redis_client",
        "//backend/common:validation",
        "//backend/frontend_service:ldap_loader",
        "//backend/historical_data:constants",
        "@pypi//tenacity",
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
        "//backend/common:api_response_wrapper",
        "//backend/historical_data:gerrit_history_fetcher",
        "//backend/historical_data:google_calendar_history_fetcher",
        "//backend/historical_data:google_chat_history_fetcher",
        "//backend/utils:date_time_util",
        "@pypi//flask",
    ],
)

py_library(
    name = "google_chat_history_fetcher",
    srcs = [
        "google_chat_history_fetcher.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:google_client",
        "//backend/utils:google_chat_message_store",
        "//backend/utils:google_chat_utils",
    ],
)

py_library(
    name = "gerrit_history_fetcher",
    srcs = [
        "gerrit_history_fetcher.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:gerrit_client",
        "//backend/common:redis_client",
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
