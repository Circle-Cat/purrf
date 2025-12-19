load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_test(
    name = "profile_mapper_test",
    srcs = ["profile_mapper_test.py"],
    deps = ["//backend/profile"],
)

py_test(
    name = "profile_query_service_test",
    srcs = ["profile_query_service_test.py"],
    deps = ["//backend/profile"],
)

py_test(
    name = "profile_command_service_test",
    srcs = ["profile_command_service_test.py"],
    deps = [
        "//backend/profile",
    ],
)

py_test(
    name = "profile_service_test",
    srcs = ["profile_service_test.py"],
    deps = [
        "//backend/common:constants",
        "//backend/profile",
    ],
)

py_test(
    name = "profile_controller_test",
    srcs = ["profile_controller_test.py"],
    deps = [
        "//backend/profile",
        "@pypi//fastapi",
        "@pypi//httpx",
        "@pypi//starlette",
    ],
)
