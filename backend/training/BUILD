load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "training_course_service",
    srcs = ["training_course_service.py"],
    deps = [
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/repository:repositories",
    ],
)

py_library(
    name = "training_assignment_service",
    srcs = ["training_assignment_service.py"],
    deps = [
        "//backend/common:exceptions",
        "//backend/common:mentorship_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/repository:repositories",
    ],
)

py_library(
    name = "training_admin_controller",
    srcs = ["training_admin_controller.py"],
    deps = [
        ":training_assignment_service",
        ":training_course_service",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)
