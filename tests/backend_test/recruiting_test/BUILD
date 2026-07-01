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

py_test(
    name = "cooldown_test",
    srcs = ["cooldown_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/recruiting",
    ],
)

py_test(
    name = "resume_storage_test",
    srcs = ["resume_storage_test.py"],
    deps = [
        "//backend/recruiting",
        "@pypi//google_api_core",
    ],
)

py_test(
    name = "application_service_test",
    srcs = ["application_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)
