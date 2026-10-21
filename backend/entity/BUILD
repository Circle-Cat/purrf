load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "entities",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:approval_enums",
        "//backend/common:base",
        "//backend/common:leave_enums",
        "//backend/common:mentorship_email_enums",
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/common:user_enums",
        "@pypi//sqlalchemy",
    ],
)
