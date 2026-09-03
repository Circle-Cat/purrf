load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "training_course_service_test",
    srcs = ["training_course_service_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/training:training_course_service",
    ],
)

py_test(
    name = "training_assignment_service_test",
    srcs = ["training_assignment_service_test.py"],
    deps = [
        "//backend/common:exceptions",
        "//backend/common:mentorship_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/training:training_assignment_service",
    ],
)

py_test(
    name = "training_admin_controller_test",
    srcs = ["training_admin_controller_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/training:training_admin_controller",
    ],
)
