load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "google_calendar_history_fetcher_test",
    srcs = ["google_calendar_history_fetcher_test.py"],
    deps = [
        "//src/historical_data:google_calendar_history_fetcher",
    ],
)

py_test(
    name = "microsoft_ldap_fetcher_test",
    srcs = ["microsoft_ldap_fetcher_test.py"],
    deps = [
        "//src/historical_data:microsoft_ldap_fetcher",
    ],
)

py_test(
    name = "historical_api_test",
    srcs = ["historical_api_test.py"],
    deps = [
        "//src/historical_data:historical_api",
    ],
)

py_test(
    name = "google_chat_history_fetcher_test",
    srcs = ["google_chat_history_fetcher_test.py"],
    deps = [
        "//src/historical_data:google_chat_history_fetcher",
    ],
)

py_test(
    name = "gerrit_history_fetcher_test",
    srcs = ["gerrit_history_fetcher_test.py"],
    deps = [
        "//src/common:gerrit_client",
        "//src/historical_data:gerrit_history_fetcher",
        "@pypi//redis",
    ],
)

py_test(
    name = "microsoft_chat_history_fetcher_test",
    srcs = ["microsoft_chat_history_fetcher_test.py"],
    deps = [
        "//src/historical_data:microsoft_chat_history_fetcher",
    ],
)
