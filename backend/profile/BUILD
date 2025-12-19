load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "profile",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:constants",
        "//backend/common:fast_api_response_wrapper",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
        "@pypi//sqlalchemy",
    ],
)
