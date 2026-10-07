load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "approval_service_test",
    srcs = ["approval_service_test.py"],
    deps = [
        "//backend/approval:approval_handler",
        "//backend/approval:approval_service",
        "//backend/common:approval_enums",
        "//backend/common:exceptions",
        "//backend/common:permissions",
        "//backend/entity:entities",
        "@pypi//sqlalchemy",
    ],
)
