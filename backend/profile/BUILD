load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "profile_mapper",
    srcs = ["profile_mapper.py"],
    deps = [
        "//backend/dto",
        "//backend/entity:entities",
        "@pypi//sqlalchemy",
    ],
)
