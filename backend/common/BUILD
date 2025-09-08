load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "environment_constants",
    srcs = ["environment_constants.py"],
)

py_library(
    name = "constants",
    srcs = ["constants.py"],
)

py_library(
    name = "logger",
    srcs = ["logger.py"],
    deps = ["//backend/common:environment_constants"],
)

py_library(
    name = "google_client",
    srcs = [
        "google_client.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:logger",
        "@pypi//google_api_python_client",
        "@pypi//google_auth_oauthlib",
        "@pypi//google_cloud_pubsub",
        "@pypi//grpcio",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "redis_client",
    srcs = ["redis_client.py"],
    deps = [
        "//backend/common:constants",
        "//backend/common:logger",
        "@pypi//redis",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "api_response_wrapper",
    srcs = [
        "api_response_wrapper.py",
    ],
    deps = [
        "@pypi//flask",
    ],
)

py_library(
    name = "error_handler",
    srcs = [
        "error_handler.py",
    ],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/common:logger",
    ],
)

py_library(
    name = "gerrit_client",
    srcs = [
        "gerrit_client.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:logger",
        "@pypi//requests",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "jira_client",
    srcs = [
        "jira_client.py",
    ],
    deps = [
        "//backend/common:logger",
        "@pypi//jira",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "validation",
    srcs = ["validation.py"],
    data = [
        "//backend/schemas",
    ],
    deps = [
        "//backend/common:logger",
        "@pypi//jsonschema",
    ],
)

py_library(
    name = "json_schema_validator",
    srcs = ["json_schema_validator.py"],
    data = [
        "//backend/schemas",
    ],
    deps = [
        "//backend/common:logger",
        "@pypi//jsonschema",
    ],
)

py_library(
    name = "asyncio_event_loop_manager",
    srcs = ["asyncio_event_loop_manager.py"],
    deps = [
        "//backend/common:logger",
    ],
)

py_library(
    name = "microsoft_graph_service_client",
    srcs = [
        "microsoft_graph_service_client.py",
    ],
    deps = [
        "//backend/common:constants",
        "@pypi//azure_identity",
        "@pypi//msgraph_sdk",
    ],
)
