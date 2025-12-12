load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_test(
    name = "authentication_service_test",
    srcs = ["authentication_service_test.py"],
    deps = [
        "//backend/authentication:authentication_service",
    ],
)

py_test(
    name = "authentication_controller_test",
    srcs = ["authentication_controller_test.py"],
    deps = [
        "//backend/authentication:authentication_controller",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)
