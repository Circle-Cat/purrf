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
        "//backend/historical_data:constants",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_ldap_fetcher",
    srcs = [
        "microsoft_ldap_fetcher.py",
    ],
    deps = [
        "//backend/common:microsoft_client",
        "//backend/common:redis_client",
    ],
)

py_library(
    name = "historical_api",
    srcs = ["historical_api.py"],
    deps = [
        "//backend/historical_data:gerrit_history_fetcher",
        "//backend/historical_data:google_calendar_history_fetcher",
        "//backend/historical_data:google_chat_history_fetcher",
        "//backend/historical_data:jira_history_fetcher",
        "//backend/historical_data:microsoft_chat_history_fetcher",
        "//backend/historical_data:microsoft_ldap_fetcher",
        "//backend/utils:date_time_parser",
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
    name = "microsoft_chat_history_fetcher",
    srcs = [
        "microsoft_chat_history_fetcher.py",
    ],
    deps = [
        "//backend/common:microsoft_client",
        "//backend/historical_data:microsoft_ldap_fetcher",
        "//backend/utils:microsoft_chat_message_store",
    ],
)

py_library(
    name = "jira_history_fetcher",
    srcs = [
        "jira_history_fetcher.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:jira_client",
        "//backend/common:logger",
        "//backend/common:redis_client",
        "//backend/frontend_service:ldap_loader",
        "@pypi//jira",
    ],
)
