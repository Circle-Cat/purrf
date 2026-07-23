load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "logger_test",
    srcs = ["logger_test.py"],
    deps = [
        "//backend/common:logger",
    ],
)

py_test(
    name = "permissions_test",
    srcs = ["permissions_test.py"],
    deps = [
        "//backend/common:permissions",
    ],
)

py_test(
    name = "permission_descriptions_test",
    srcs = ["permission_descriptions_test.py"],
    deps = [
        "//backend/common:permission_descriptions",
        "//backend/common:permissions",
    ],
)

py_test(
    name = "recruiting_enums_test",
    srcs = ["recruiting_enums_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/common:recruiting_enums",
    ],
)

py_test(
    name = "auth0_client_test",
    srcs = ["auth0_client_test.py"],
    deps = [
        "//backend/common:auth0_client",
        "//backend/common:exceptions",
        "@pypi//pyjwt",
    ],
)

py_test(
    name = "google_client_test",
    srcs = ["google_client_test.py"],
    deps = [
        "//backend/common:google_client",
    ],
)

py_test(
    name = "gmail_client_test",
    srcs = ["gmail_client_test.py"],
    deps = [
        "//backend/common:exceptions",
        "//backend/common:gmail_client",
        "@pypi//google_api_python_client",
        "@pypi//google_auth",
    ],
)

py_test(
    name = "redis_client_test",
    srcs = ["redis_client_test.py"],
    deps = [
        "//backend/common:redis_client",
    ],
)

py_test(
    name = "fast_api_error_handler_test",
    srcs = ["fast_api_error_handler_test.py"],
    deps = [
        "//backend/common:exceptions",
        "//backend/common:fast_api_error_handler",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "fast_api_response_wrapper_test",
    srcs = ["fast_api_response_wrapper_test.py"],
    deps = [
        "//backend/common:fast_api_response_wrapper",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "gerrit_client_test",
    srcs = ["gerrit_client_test.py"],
    deps = [
        "//backend/common:gerrit_client",
    ],
)

py_test(
    name = "jira_client_test",
    srcs = ["jira_client_test.py"],
    deps = [
        "//backend/common:jira_client",
    ],
)

py_test(
    name = "validation_test",
    srcs = ["validation_test.py"],
    deps = [
        "//backend/common:validation",
    ],
)

py_test(
    name = "json_schema_validator_test",
    srcs = ["json_schema_validator_test.py"],
    deps = [
        "//backend/common:json_schema_validator",
    ],
)

py_test(
    name = "asyncio_event_loop_manager_test",
    srcs = ["asyncio_event_loop_manager_test.py"],
    deps = [
        "//backend/common:asyncio_event_loop_manager",
    ],
)

py_test(
    name = "launchdarkly_client_test",
    srcs = ["launchdarkly_client_test.py"],
    deps = [
        "//backend/common:launchdarkly_client",
    ],
)

py_test(
    name = "microsoft_graph_service_client_test",
    srcs = ["microsoft_graph_service_client_test.py"],
    deps = [
        "//backend/common:microsoft_graph_service_client",
    ],
)

py_test(
    name = "database_test",
    srcs = ["database_test.py"],
    deps = [
        "//backend/common:database",
    ],
)

py_test(
    name = "name_utils_test",
    srcs = ["name_utils_test.py"],
    deps = [
        "//backend/common:name_utils",
    ],
)

py_test(
    name = "trusted_connections_test",
    srcs = ["trusted_connections_test.py"],
    deps = [
        "//backend/common:trusted_connections",
    ],
)

py_test(
    name = "identity_type_test",
    srcs = ["identity_type_test.py"],
    deps = [
        "//backend/common:identity_type",
    ],
)
