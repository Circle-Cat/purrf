load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "authentication_controller",
    srcs = ["authentication_controller.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)

py_library(
    name = "authentication_service",
    srcs = ["authentication_service.py"],
    deps = [
        "//backend/common:environment_constants",
        "//backend/common:user_role",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//google_auth_oauthlib",
        "@pypi//pyjwt",
    ],
)
