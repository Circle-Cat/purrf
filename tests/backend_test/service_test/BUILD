load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "microsoft_service_test",
    srcs = ["microsoft_service_test.py"],
    deps = [
        "//backend/service:microsoft_service",
    ],
)

py_test(
    name = "jira_search_service_test",
    srcs = ["jira_search_service_test.py"],
    deps = [
        "//backend/service:jira_search_service",
    ],
)
