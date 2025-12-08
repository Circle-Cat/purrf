load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "dto",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/entity:entities",
    ],
)
