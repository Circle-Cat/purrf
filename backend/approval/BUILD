load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "approval_handler",
    srcs = ["approval_handler.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/entity:entities",
    ],
)

py_library(
    name = "approval_service",
    srcs = ["approval_service.py"],
    deps = [
        ":approval_handler",
        "//backend/common:approval_enums",
        "//backend/common:exceptions",
        "//backend/entity:entities",
        "//backend/notification_management:event_recorder",
        "@pypi//sqlalchemy",
    ],
)
