load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_test(
    name = "authentication_service_test",
    srcs = ["authentication_service_test.py"],
    deps = [
        "//backend/authentication:authentication_service",
        "//backend/common:identity_type",
        "//backend/dto",
    ],
)

py_test(
    name = "email_management_service_test",
    srcs = ["email_management_service_test.py"],
    deps = [
        "//backend/authentication:email_management_service",
        "//backend/common:exceptions",
        "//backend/common:identity_type",
        "//backend/entity:entities",
        "@pypi//pyjwt",
    ],
)

py_test(
    name = "email_management_controller_test",
    srcs = ["email_management_controller_test.py"],
    deps = [
        "//backend/authentication:email_management_controller",
        "//backend/common:api_endpoints",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "authentication_controller_test",
    srcs = ["authentication_controller_test.py"],
    deps = [
        "//backend/authentication:authentication_controller",
        "//backend/common:api_endpoints",
        "//backend/common:identity_type",
        "//backend/common:permissions",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)
