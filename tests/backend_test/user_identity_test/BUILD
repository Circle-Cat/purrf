load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "user_identity_service_test",
    srcs = ["user_identity_service_test.py"],
    deps = [
        "//backend/common:identity_type",
        "//backend/common:permissions",
        "//backend/user_identity:user_identity_service",
    ],
)
