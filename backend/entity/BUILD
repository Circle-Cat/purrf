load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "entities",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:base",
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "@pypi//sqlalchemy",
    ],
)
