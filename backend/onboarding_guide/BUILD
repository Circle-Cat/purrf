load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "guide_progress_service",
    srcs = ["guide_progress_service.py"],
    deps = [
        "//backend/common:onboarding_guide_enums",
        "//backend/dto",
        "@pypi//sqlalchemy",
    ],
)

py_library(
    name = "guide_progress_controller",
    srcs = ["guide_progress_controller.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)
