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
    name = "recruiting_mapper_test",
    srcs = ["recruiting_mapper_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
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
    name = "stage_machine_test",
    srcs = ["stage_machine_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/recruiting",
    ],
)

py_test(
    name = "evaluation_rubric_test",
    srcs = ["evaluation_rubric_test.py"],
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
        "@pypi//google_cloud_storage",
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

py_test(
    name = "application_controller_test",
    srcs = ["application_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
        "@pypi//python_multipart",
    ],
)

py_test(
    name = "pipeline_owners_test",
    srcs = ["pipeline_owners_test.py"],
    deps = [
        "//backend/recruiting",
    ],
)

py_test(
    name = "board_service_test",
    srcs = ["board_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "evaluation_service_test",
    srcs = ["evaluation_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "board_controller_test",
    srcs = ["board_controller_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "blacklist_service_test",
    srcs = ["blacklist_service_test.py"],
    deps = [
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "blacklist_controller_test",
    srcs = ["blacklist_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "evaluation_controller_test",
    srcs = ["evaluation_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
    ],
)
