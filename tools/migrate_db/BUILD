load("@rules_python//python:defs.bzl", "py_binary", "py_library")

py_library(
    name = "make_migration_lib",
    srcs = ["make_migration.py"],
    visibility = ["//tests:__subpackages__"],
    deps = [
        "@pypi//alembic",
    ],
)

py_binary(
    name = "make_migration",
    srcs = ["make_migration.py"],
    deps = [
        "//backend/common:base",
        "//backend/common:logger",
        "//backend/entity:entities",
        "@pypi//alembic",
        "@pypi//alembic_postgresql_enum",
        "@pypi//asyncpg",
        "@pypi//sqlalchemy",
    ],
)

py_library(
    name = "migrate_db_lib",
    srcs = ["migrate_db.py"],
    visibility = ["//tests:__subpackages__"],
    deps = [
        "@pypi//alembic",
    ],
)

py_binary(
    name = "migrate_db",
    srcs = ["migrate_db.py"],
    deps = [
        "//backend/common:base",
        "//backend/common:database",
        "//backend/common:logger",
        "//backend/entity:entities",
        "@pypi//alembic",
        "@pypi//alembic_postgresql_enum",
        "@pypi//asyncpg",
        "@pypi//sqlalchemy",
    ],
)
