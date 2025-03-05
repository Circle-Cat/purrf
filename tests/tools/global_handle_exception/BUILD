load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_exception_handler",
    srcs = ["test_exception_handler.py"],
    deps = [
        "//tools/global_handle_exception:exception_handler",
        "@pypi//flask",
    ],
)
