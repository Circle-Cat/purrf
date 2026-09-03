load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_test(
    name = "mentorship_mapper_test",
    srcs = ["mentorship_mapper_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "mentorship_controller_test",
    srcs = ["mentorship_controller_test.py"],
    deps = [
        "//backend/mentorship",
        "@pypi//httpx",
    ],
)

py_test(
    name = "rounds_service_test",
    srcs = ["rounds_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "participation_service_test",
    srcs = ["participation_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "registration_service_test",
    srcs = ["registration_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "meeting_service_test",
    srcs = ["meeting_service_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/mentorship",
    ],
)

py_test(
    name = "meet_attendance_service_test",
    srcs = ["meet_attendance_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "mentorship_admin_service_test",
    srcs = ["mentorship_admin_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "mentorship_admin_controller_test",
    srcs = ["mentorship_admin_controller_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "onboarding_training_service_test",
    srcs = ["onboarding_training_service_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/mentorship",
    ],
)

py_test(
    name = "notification_renderers_test",
    srcs = ["notification_renderers_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/mentorship",
        "//backend/notification_management:render_registry",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)

py_test(
    name = "recipient_resolvers_test",
    srcs = ["recipient_resolvers_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/mentorship",
        "//backend/notification_management:recipient_registry",
        "//backend/notification_management:render_registry",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)

py_test(
    name = "mentorship_admission_service_test",
    srcs = ["mentorship_admission_service_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/mentorship",
        "//backend/repository:repositories",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)
