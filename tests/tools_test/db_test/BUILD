load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "init_db_test",
    srcs = ["init_db_test.py"],
    deps = [
        "//tools:init_db_lib",
    ],
)

py_test(
    name = "make_migration_test",
    srcs = ["make_migration_test.py"],
    deps = [
        "//tools/migrate_db:make_migration_lib",
    ],
)

py_test(
    name = "migrate_db_test",
    srcs = ["migrate_db_test.py"],
    deps = [
        "//tools/migrate_db:migrate_db_lib",
    ],
)
