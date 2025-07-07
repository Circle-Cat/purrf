load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "frontend_api",
    srcs = ["frontend_api.py"],
    deps = [
        "//src/common:api_response_wrapper",
        "//src/common:constants",
        "//src/frontend_service:chat_query_utils",
        "//src/utils:google_chat_utils",
        "//src/frontend_service:ldap_loader",
        "@pypi//flask",
    ],
)

py_library(
    name = "ldap_loader",
    srcs = [
        "ldap_loader.py",
    ],
    deps = [
        "//src/common:redis_client",
    ],
)

py_library(
    name = "chat_query_utils",
    srcs = ["chat_query_utils.py"],
    deps = [
        "//src/common:constants",
        "//src/common:logger",
        "//src/common:redis_client",
        "//src/frontend_service:ldap_loader",
        "//src/utils:google_chat_utils",
        "@pypi//python_dateutil",
    ],
)
