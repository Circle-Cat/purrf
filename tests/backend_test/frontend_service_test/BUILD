load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "frontend_controller_test",
    srcs = ["frontend_controller_test.py"],
    deps = [
        "//backend/common:constants",
        "//backend/frontend_service:frontend_controller",
        "@pypi//flask",
    ],
)

py_test(
    name = "ldap_loader_test",
    srcs = ["ldap_loader_test.py"],
    deps = [
        "//backend/frontend_service:ldap_loader",
    ],
)

py_test(
    name = "chat_query_utils_test",
    srcs = ["chat_query_utils_test.py"],
    deps = [
        "//backend/common:constants",
        "//backend/frontend_service:chat_query_utils",
    ],
)

py_test(
    name = "microsoft_chat_topics_loader_test",
    srcs = ["microsoft_chat_topics_loader_test.py"],
    deps = [
        "//backend/frontend_service:microsoft_chat_topics_loader",
    ],
)

py_test(
    name = "jira_loader_test",
    srcs = ["jira_loader_test.py"],
    deps = [
        "//backend/frontend_service:jira_loader",
    ],
)

py_test(
    name = "gerrit_loader_test",
    srcs = ["gerrit_loader_test.py"],
    deps = [
        "//backend/common:constants",
        "//backend/frontend_service:gerrit_loader",
    ],
)

py_test(
    name = "calendar_loader_test",
    srcs = ["calendar_loader_test.py"],
    deps = [
        "//backend/frontend_service:calendar_loader",
    ],
)

py_test(
    name = "ldap_lookup_service_test",
    srcs = ["ldap_lookup_service_test.py"],
    deps = [
        "//backend/frontend_service:ldap_lookup_service",
    ],
)
