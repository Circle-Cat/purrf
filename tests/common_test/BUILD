load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "logger_test",
    srcs = ["logger_test.py"],
    deps = [
        "//src/common:logger",
    ],
)

py_test(
    name = "google_client_test",
    srcs = ["google_client_test.py"],
    deps = [
        "//src/common:google_client",
    ],
)

py_test(
    name = "redis_client_test",
    srcs = ["redis_client_test.py"],
    deps = [
        "//src/common:redis_client",
    ],
)

py_test(
    name = "api_response_wrapper_test",
    srcs = ["api_response_wrapper_test.py"],
    deps = [
        "//src/common:api_response_wrapper",
        "@pypi//flask",
    ],
)

py_test(
    name = "error_handler_test",
    srcs = ["error_handler_test.py"],
    deps = [
        "//src/common:error_handler",
        "@pypi//flask",
    ],
)

py_test(
    name = "gerrit_client_test",
    srcs = ["gerrit_client_test.py"],
    deps = [
        "//src/common:gerrit_client",
    ],
)

py_test(
    name = "microsoft_client_test",
    srcs = ["microsoft_client_test.py"],
    deps = [
        "//src/common:microsoft_client",
    ],
)
