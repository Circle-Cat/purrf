load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "recruiting",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:mentorship_enums",
        "//backend/common:permissions",
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
        "@pypi//google_api_core",
        "@pypi//python_multipart",
        "@pypi//sqlalchemy",
    ],
)
