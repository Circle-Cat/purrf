load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "communication",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:communication_enums",
        "//backend/common:environment_constants",
        "//backend/common:exceptions",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)
