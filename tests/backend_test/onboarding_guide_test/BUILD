load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "guide_progress_service_test",
    srcs = ["guide_progress_service_test.py"],
    deps = [
        "//backend/common:onboarding_guide_enums",
        "//backend/onboarding_guide:guide_progress_service",
    ],
)

py_test(
    name = "guide_progress_controller_test",
    srcs = ["guide_progress_controller_test.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_error_handler",
        "//backend/common:onboarding_guide_enums",
        "//backend/dto",
        "//backend/onboarding_guide:guide_progress_controller",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)
