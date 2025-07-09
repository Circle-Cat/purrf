load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "frontend_api_test",
    srcs = ["frontend_api_test.py"],
    deps = [
        "//src/common:constants",
        "//src/frontend_service:frontend_api",
        "@pypi//flask",
    ],
)

py_test(
    name = "ldap_loader_test",
    srcs = ["ldap_loader_test.py"],
    deps = [
        "//src/frontend_service:ldap_loader",
    ],
)

py_test(
    name = "chat_query_utils_test",
    srcs = ["chat_query_utils_test.py"],
    deps = [
        "//src/common:constants",
        "//src/frontend_service:chat_query_utils",
    ],
)

py_test(
    name = "microsoft_chat_topics_loader_test",
    srcs = ["microsoft_chat_topics_loader_test.py"],
    deps = [
        "//src/frontend_service:microsoft_chat_topics_loader",
    ],
)
