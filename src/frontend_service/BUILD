load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "frontend_api",
    srcs = ["frontend_api.py"],
    deps = [
        "//src/common:api_response_wrapper",
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
