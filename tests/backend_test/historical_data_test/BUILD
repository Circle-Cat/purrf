load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "google_calendar_sync_service_test",
    srcs = ["google_calendar_sync_service_test.py"],
    deps = [
        "//backend/historical_data:google_calendar_sync_service",
    ],
)

py_test(
    name = "historical_controller_test",
    srcs = ["historical_controller_test.py"],
    deps = [
        "//backend/historical_data:historical_controller",
    ],
)

py_test(
    name = "google_chat_history_fetcher_test",
    srcs = ["google_chat_history_fetcher_test.py"],
    deps = [
        "//backend/historical_data:google_chat_history_fetcher",
    ],
)

py_test(
    name = "gerrit_history_fetcher_test",
    srcs = ["gerrit_history_fetcher_test.py"],
    deps = [
        "//backend/common:gerrit_client",
        "//backend/historical_data:gerrit_history_fetcher",
        "@pypi//redis",
    ],
)

py_test(
    name = "microsoft_chat_history_sync_service_test",
    srcs = ["microsoft_chat_history_sync_service_test.py"],
    deps = [
        "//backend/historical_data:microsoft_chat_history_sync_service",
    ],
)

py_test(
    name = "microsoft_member_sync_service_test",
    srcs = ["microsoft_member_sync_service_test.py"],
    deps = [
        "//backend/historical_data:microsoft_member_sync_service",
    ],
)

py_test(
    name = "jira_history_sync_service_test",
    srcs = ["jira_history_sync_service_test.py"],
    deps = [
        "//backend/historical_data:jira_history_sync_service",
    ],
)
