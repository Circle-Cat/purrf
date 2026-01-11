load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "internal_activity_controller_test",
    srcs = ["internal_activity_controller_test.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:constants",
        "//backend/common:user_role",
        "//backend/internal_activity_service:internal_activity_controller",
        "//backend/utils:auth_middleware",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "google_chat_analytics_service_test",
    srcs = ["google_chat_analytics_service_test.py"],
    deps = [
        "//backend/internal_activity_service:google_chat_analytics_service",
    ],
)

py_test(
    name = "microsoft_meeting_chat_topic_cache_service_test",
    srcs = ["microsoft_meeting_chat_topic_cache_service_test.py"],
    deps = [
        "//backend/internal_activity_service:microsoft_meeting_chat_topic_cache_service",
    ],
)

py_test(
    name = "gerrit_analytics_service_test",
    srcs = ["gerrit_analytics_service_test.py"],
    deps = [
        "//backend/common:constants",
        "//backend/internal_activity_service:gerrit_analytics_service",
    ],
)

py_test(
    name = "google_calendar_analytics_service_test",
    srcs = ["google_calendar_analytics_service_test.py"],
    deps = [
        "//backend/internal_activity_service:google_calendar_analytics_service",
    ],
)

py_test(
    name = "ldap_service_test",
    srcs = ["ldap_service_test.py"],
    deps = [
        "//backend/internal_activity_service:ldap_service",
    ],
)

py_test(
    name = "microsoft_chat_analytics_service_test",
    srcs = ["microsoft_chat_analytics_service_test.py"],
    deps = [
        "//backend/internal_activity_service:microsoft_chat_analytics_service",
    ],
)

py_test(
    name = "jira_analytics_service_test",
    srcs = ["jira_analytics_service_test.py"],
    deps = [
        "//backend/internal_activity_service:jira_analytics_service",
    ],
)

py_test(
    name = "summary_service_test",
    srcs = ["summary_service_test.py"],
    deps = [
        "//backend/internal_activity_service:summary_service",
    ],
)
