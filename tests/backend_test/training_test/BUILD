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
        "//backend/common:mentorship_enums",
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/training:training_admin_controller",
    ],
)

py_test(
    name = "training_progress_service_test",
    srcs = ["training_progress_service_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/training:training_progress_service",
    ],
)

py_test(
    name = "completion_test",
    srcs = ["completion_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/training:completion",
    ],
)

py_test(
    name = "scorm_manifest_test",
    srcs = ["scorm_manifest_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/training:scorm_manifest",
    ],
)

py_test(
    name = "scorm_package_test",
    srcs = ["scorm_package_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/training:scorm_manifest",
        "//backend/training:scorm_package",
    ],
)

py_test(
    name = "byte_range_test",
    srcs = ["byte_range_test.py"],
    deps = ["//backend/training:byte_range"],
)

py_test(
    name = "content_host_test",
    srcs = ["content_host_test.py"],
    deps = ["//backend/training:content_host"],
)

py_test(
    name = "training_content_token_test",
    srcs = ["training_content_token_test.py"],
    deps = ["//backend/training:training_content_token"],
)

py_test(
    name = "training_storage_test",
    srcs = ["training_storage_test.py"],
    deps = [
        "//backend/training:training_storage",
        "@pypi//google_api_core",
    ],
)

py_test(
    name = "training_content_service_test",
    srcs = ["training_content_service_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/training:byte_range",
        "//backend/training:training_content_service",
        "//backend/training:training_content_token",
        "//backend/training:training_storage",
    ],
)

py_test(
    name = "training_content_controller_test",
    srcs = ["training_content_controller_test.py"],
    deps = [
        "//backend/training:byte_range",
        "//backend/training:content_host",
        "//backend/training:training_content_controller",
        "//backend/training:training_content_service",
        "//backend/training:training_content_token",
        "@pypi//starlette",
    ],
)

py_test(
    name = "training_package_service_test",
    srcs = ["training_package_service_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/training:scorm_manifest",
        "//backend/training:scorm_package",
        "//backend/training:training_package_service",
    ],
)
