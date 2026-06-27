load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "dto",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:identity_type",
        "//backend/common:mentorship_enums",
        "//backend/common:permissions",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "@pypi//pydantic",
    ],
)
