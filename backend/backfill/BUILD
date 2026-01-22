load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_binary(
    name = "backfill_mentorship_records",
    srcs = [
        "backfill_mentorship_records.py",
    ],
    data = [
        "Mentee.csv",
        "Mentor.csv",
        "Rounds.csv",
    ],
    deps = [
        "//backend/common:database",
        "//backend/common:logger",
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "@pypi//asyncpg",
        "@pypi//openpyxl",
        "@pypi//pandas",
        "@pypi//requests",
        "@pypi//sqlalchemy",
    ],
)

py_binary(
    name = "export_mentorship_records",
    srcs = [
        "export_mentorship_records.py",
    ],
    deps = [
        "//backend/common:database",
        "//backend/common:logger",
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "@pypi//asyncpg",
        "@pypi//openpyxl",
        "@pypi//pandas",
        "@pypi//sqlalchemy",
    ],
)
