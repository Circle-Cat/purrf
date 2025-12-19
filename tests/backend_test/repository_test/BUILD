load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_library(
    name = "base_repository_test_lib",
    testonly = True,
    srcs = ["base_repository_test_lib.py"],
    deps = [
        "//backend/common:database",
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "@pypi//asyncpg",
        "@pypi//fastapi",
    ],
)

py_test(
    name = "users_repository_test",
    srcs = ["users_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "training_repository_test",
    srcs = ["training_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "experience_repository_test",
    srcs = ["experience_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)
