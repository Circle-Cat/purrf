load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "microsoft_service",
    srcs = ["microsoft_service.py"],
    deps = [
        "//src/common:constants",
        "//src/utils:retry_utils",
        "@pypi//msgraph_sdk",
    ],
)
