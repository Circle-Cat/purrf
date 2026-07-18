load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "user_identity_service",
    srcs = ["user_identity_service.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/dto",
        "//backend/entity:entities",
    ],
)

py_library(
    name = "internal_lifecycle",
    srcs = ["internal_lifecycle.py"],
    deps = [
        "//backend/common:permissions",
    ],
)
