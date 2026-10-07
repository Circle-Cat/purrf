load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "repositories",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:approval_enums",
        "//backend/common:communication_enums",
        "//backend/common:mentorship_enums",
        "//backend/common:user_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "@pypi//asyncpg",
        "@pypi//sqlalchemy",
    ],
)
