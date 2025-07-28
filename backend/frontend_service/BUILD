load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "frontend_controller",
    srcs = ["frontend_controller.py"],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/common:constants",
        "//backend/frontend_service:calendar_loader",
        "//backend/frontend_service:chat_query_utils",
        "//backend/frontend_service:gerrit_loader",
        "//backend/frontend_service:jira_loader",
        "//backend/frontend_service:ldap_loader",
        "//backend/utils:google_chat_utils",
        "@pypi//flask",
    ],
)

py_library(
    name = "ldap_loader",
    srcs = [
        "ldap_loader.py",
    ],
    deps = [
        "//backend/common:redis_client",
    ],
)

py_library(
    name = "chat_query_utils",
    srcs = ["chat_query_utils.py"],
    deps = [
        "//backend/common:constants",
        "//backend/common:logger",
        "//backend/common:redis_client",
        "//backend/frontend_service:ldap_loader",
        "//backend/utils:google_chat_utils",
        "@pypi//python_dateutil",
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
    name = "jira_loader",
    srcs = [
        "jira_loader.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:redis_client",
        "//backend/utils:date_time_util",
    ],
)

py_library(
    name = "gerrit_loader",
    srcs = [
        "gerrit_loader.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:redis_client",
        "//backend/frontend_service:ldap_loader",
    ],
)

py_library(
    name = "calendar_loader",
    srcs = [
        "calendar_loader.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:redis_client",
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
