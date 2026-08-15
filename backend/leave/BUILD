load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "employment_profile",
    srcs = ["employment_profile.py"],
)

py_library(
    name = "coverage_report",
    srcs = ["coverage_report.py"],
    deps = [
        ":employment_profile",
    ],
)

py_library(
    name = "employment_sync_service",
    srcs = ["employment_sync_service.py"],
    deps = [
        ":coverage_report",
        ":employment_profile",
        "//backend/common:constants",
    ],
)
