load("@rules_python//python:defs.bzl", "py_binary", "py_library")

py_library(
    name = "init_db_lib",
    srcs = ["init_db.py"],
    visibility = ["//tests:__subpackages__"],
    deps = [
        "@pypi//alembic",
        "@pypi//sqlalchemy",
    ],
)

py_binary(
    name = "init_db",
    srcs = ["init_db.py"],
    data = ["//:alembic_files"],
    deps = [
        "//backend/common:base",
        "//backend/common:database",
        "//backend/common:logger",
        "//backend/entity:entities",
        "@pypi//alembic",
        "@pypi//alembic_postgresql_enum",
        "@pypi//asyncpg",
        "@pypi//mako",
        "@pypi//sqlalchemy",
    ],
)

py_binary(
    name = "dump_matching_payload",
    srcs = ["dump_matching_payload.py"],
    deps = [
        "//backend/common:database",
        "//backend/common:logger",
        "//backend/entity:entities",
        "//backend/mentorship",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)
