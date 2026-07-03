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
    name = "user_permissions_repository_test",
    srcs = ["user_permissions_repository_test.py"],
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

py_test(
    name = "job_repository_test",
    srcs = ["job_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
        "//backend/common:recruiting_enums",
    ],
)

py_test(
    name = "job_review_repository_test",
    srcs = ["job_review_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
    ],
)

py_test(
    name = "preferences_repository_test",
    srcs = ["preferences_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "mentorship_round_repository_test",
    srcs = ["mentorship_round_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "mentorship_round_participants_repository_test",
    srcs = ["mentorship_round_participants_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "mentorship_pairs_repository_test",
    srcs = ["mentorship_pairs_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "user_identities_repository_test",
    srcs = ["user_identities_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "user_emails_repository_test",
    srcs = ["user_emails_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
    ],
)

py_test(
    name = "application_repository_test",
    srcs = ["application_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/repository:repositories",
    ],
)

py_test(
    name = "application_assignment_repository_test",
    srcs = ["application_assignment_repository_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        ":base_repository_test_lib",
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/repository:repositories",
    ],
)
