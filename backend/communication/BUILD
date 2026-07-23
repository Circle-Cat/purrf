load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "communication",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:communication_enums",
        "//backend/dto",
    ],
)
