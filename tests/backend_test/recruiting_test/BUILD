load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "job_service_test",
    srcs = ["job_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "recruiting_controller_test",
    srcs = ["recruiting_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
    ],
)
