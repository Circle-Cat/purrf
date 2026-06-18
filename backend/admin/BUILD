load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "permission_admin_service",
    srcs = ["permission_admin_service.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/dto",
    ],
)
