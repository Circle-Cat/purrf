load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_api_response_wrapper",
    srcs = ["test_api_response_wrapper.py"],
    deps = [
        "//tools:api_response_wrapper",
        "@pypi//flask",
    ],
)
