load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "profile",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/dto",
        "//backend/entity:entities",
        "@pypi//sqlalchemy",
    ],
)
