load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "backfill_mentorship_records",
    srcs = [
        "backfill_mentorship_records.py",
    ],
    deps = [
        "@pypi//openpyxl",
        "@pypi//pandas",
        "@pypi//requests",
    ],
)
