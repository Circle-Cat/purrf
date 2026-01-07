load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "mentorship",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "//backend/user_identity:user_identity_service",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
        "@pypi//sqlalchemy",
    ],
)
