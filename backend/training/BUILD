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
    name = "scorm_manifest",
    srcs = ["scorm_manifest.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "@pypi//defusedxml",
    ],
)

py_library(
    name = "scorm_package",
    srcs = ["scorm_package.py"],
    deps = [
        ":scorm_manifest",
        "//backend/common:mentorship_enums",
    ],
)

py_library(
    name = "training_content_token",
    srcs = ["training_content_token.py"],
)

py_library(
    name = "training_storage",
    srcs = ["training_storage.py"],
    deps = [
        "@pypi//google_api_core",
        "@pypi//google_cloud_storage",
    ],
)

py_library(
    name = "training_package_service",
    srcs = ["training_package_service.py"],
    deps = [
        ":scorm_manifest",
        ":scorm_package",
        ":training_storage",
        "//backend/dto",
        "//backend/repository:repositories",
    ],
)

py_library(
    name = "training_content_service",
    srcs = ["training_content_service.py"],
    data = ["//backend/training/player:player_files"],
    deps = [
        ":scorm_package",
        ":training_content_token",
        ":training_storage",
        "//backend/repository:repositories",
    ],
)

py_library(
    name = "completion",
    srcs = ["completion.py"],
    deps = [
        "//backend/common:mentorship_enums",
    ],
)

py_library(
    name = "training_progress_service",
    srcs = ["training_progress_service.py"],
    deps = [
        ":completion",
        "//backend/common:mentorship_enums",
        "//backend/repository:repositories",
    ],
)

py_library(
    name = "training_content_controller",
    srcs = ["training_content_controller.py"],
    deps = [
        ":training_content_service",
        "//backend/common:api_endpoints",
        "@pypi//fastapi",
    ],
)

py_library(
    name = "training_admin_controller",
    srcs = ["training_admin_controller.py"],
    deps = [
        ":training_assignment_service",
        ":training_content_service",
        ":training_course_service",
        ":training_package_service",
        ":training_progress_service",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
        "@pypi//python_multipart",
    ],
)
