load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "mentorship",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:constants",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:mentorship_enums",
        "//backend/common:user_role",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "//backend/service:launchdarkly_service",
        "//backend/utils:permission_decorators",
        "@pypi//intervaltree",
        "@pypi//python_dateutil",
        "@pypi//sortedcontainers",
        "@pypi//sqlalchemy",
    ],
)
