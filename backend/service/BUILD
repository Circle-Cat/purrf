load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "microsoft_service",
    srcs = ["microsoft_service.py"],
    deps = [
        "//backend/common:constants",
        "//backend/utils:retry_utils",
        "@pypi//msgraph_sdk",
    ],
)

py_library(
    name = "jira_search_service",
    srcs = ["jira_search_service.py"],
    deps = [
        "//backend/common:constants",
        "//backend/utils:retry_utils",
        "@pypi//jira",
    ],
)
