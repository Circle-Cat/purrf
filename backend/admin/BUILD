load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "permission_admin_service",
    srcs = ["permission_admin_service.py"],
    deps = [
        "//backend/common:permission_descriptions",
        "//backend/common:permissions",
        "//backend/dto",
    ],
)

py_library(
    name = "permission_admin_controller",
    srcs = ["permission_admin_controller.py"],
    deps = [
        ":permission_admin_service",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)
