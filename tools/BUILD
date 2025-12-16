load("@rules_python//python:defs.bzl", "py_binary")

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
        "@pypi//asyncpg",
        "@pypi//mako",
        "@pypi//sqlalchemy",
    ],
)
