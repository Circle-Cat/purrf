load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "frontend_controller",
    srcs = ["frontend_controller.py"],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/common:constants",
        "@pypi//flask",
    ],
)

py_library(
    name = "google_chat_analytics_service",
    srcs = ["google_chat_analytics_service.py"],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "microsoft_meeting_chat_topic_cache_service",
    srcs = ["microsoft_meeting_chat_topic_cache_service.py"],
    deps = [
        "//backend/common:constants",
        "//backend/common:environment_constants",
    ],
)

py_library(
    name = "gerrit_analytics_service",
    srcs = [
        "gerrit_analytics_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "google_calendar_analytics_service",
    srcs = [
        "google_calendar_analytics_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "ldap_service",
    srcs = [
        "ldap_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "microsoft_chat_analytics_service",
    srcs = [
        "microsoft_chat_analytics_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "jira_analytics_service",
    srcs = [
        "jira_analytics_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "summary_service",
    srcs = [
        "summary_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)
