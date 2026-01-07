load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "logger_test",
    srcs = ["logger_test.py"],
    deps = [
        "//backend/common:logger",
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
    name = "microsoft_graph_service_client_test",
    srcs = ["microsoft_graph_service_client_test.py"],
    deps = [
        "//backend/common:microsoft_graph_service_client",
    ],
)
