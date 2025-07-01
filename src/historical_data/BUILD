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
        "//src/common:google_client",
        "//src/common:logger",
        "//src/common:redis_client",
        "//src/common:validation",
        "//src/historical_data:constants",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_ldap_fetcher",
    srcs = [
        "microsoft_ldap_fetcher.py",
    ],
    deps = [
        "//src/common:microsoft_client",
        "//src/common:redis_client",
    ],
)

py_library(
    name = "historical_api",
    srcs = ["historical_api.py"],
    deps = [
        "//src/historical_data:gerrit_history_fetcher",
        "//src/historical_data:google_calendar_history_fetcher",
        "//src/historical_data:google_chat_history_fetcher",
        "//src/historical_data:jira_history_fetcher",
        "//src/historical_data:microsoft_chat_history_fetcher",
        "//src/historical_data:microsoft_ldap_fetcher",
        "//src/utils:date_time_parser",
        "@pypi//flask",
    ],
)

py_library(
    name = "google_chat_history_fetcher",
    srcs = [
        "google_chat_history_fetcher.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:google_client",
        "//src/utils:google_chat_message_store",
        "//src/utils:google_chat_utils",
    ],
)

py_library(
    name = "gerrit_history_fetcher",
    srcs = [
        "gerrit_history_fetcher.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:gerrit_client",
        "//src/common:redis_client",
    ],
)

py_library(
    name = "microsoft_chat_history_fetcher",
    srcs = [
        "microsoft_chat_history_fetcher.py",
    ],
    deps = [
        "//src/common:microsoft_client",
        "//src/historical_data:microsoft_ldap_fetcher",
        "//src/utils:microsoft_chat_message_store",
    ],
)

py_library(
    name = "jira_history_fetcher",
    srcs = [
        "jira_history_fetcher.py",
    ],
    deps = [
        "//src/common:constants",
        "//src/common:jira_client",
        "//src/common:logger",
        "//src/common:redis_client",
        "//src/frontend_service:ldap_loader",
        "@pypi//jira",
    ],
)
