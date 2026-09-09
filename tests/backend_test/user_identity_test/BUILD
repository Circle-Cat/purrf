load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "user_identity_service_test",
    srcs = ["user_identity_service_test.py"],
    deps = [
        "//backend/common:identity_type",
        "//backend/common:permissions",
        "//backend/user_identity:user_identity_service",
    ],
)

py_test(
    name = "notification_renderers_test",
    srcs = ["notification_renderers_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:user_enums",
        "//backend/entity:entities",
        "//backend/notification_management:recipient_registry",
        "//backend/notification_management:render_registry",
        "//backend/user_identity:notification_renderers",
        "//backend/user_identity:user_recipient_resolvers",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)

py_test(
    name = "internal_onboarding_training_test",
    srcs = ["internal_onboarding_training_test.py"],
    deps = [
        "//backend/common:constants",
        "//backend/common:mentorship_enums",
        "//backend/user_identity:internal_onboarding_training",
    ],
)

py_test(
    name = "internal_lifecycle_test",
    srcs = ["internal_lifecycle_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/user_identity:internal_lifecycle",
    ],
)
