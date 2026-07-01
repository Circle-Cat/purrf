load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "job_config_dto_test",
    srcs = ["job_config_dto_test.py"],
    deps = ["//backend/dto"],
)

py_test(
    name = "job_dto_test",
    srcs = ["job_dto_test.py"],
    deps = ["//backend/dto"],
)

py_test(
    name = "application_dto_test",
    srcs = ["application_dto_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
    ],
)
