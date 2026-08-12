load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "microsoft_chat_subscription_service_test",
    srcs = ["microsoft_chat_subscription_service_test.py"],
    deps = [
        "//backend/notification_management:microsoft_chat_subscription_service",
    ],
)

py_test(
    name = "notification_controller_test",
    srcs = ["notification_controller_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/notification_management:notification_controller",
        "//backend/utils:auth_middleware",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "google_chat_subscription_service_test",
    srcs = ["google_chat_subscription_service_test.py"],
    deps = [
        "//backend/notification_management:google_chat_subscription_service",
    ],
)

py_test(
    name = "gerrit_subscription_service_test",
    srcs = ["gerrit_subscription_service_test.py"],
    deps = [
        "//backend/notification_management:gerrit_subscription_service",
        "@pypi//requests",
    ],
)

py_test(
    name = "gerrit_webhook_lib_test",
    srcs = ["gerrit_webhook_lib_test.py"],
    deps = [
        "//backend/notification_management:gerrit_webhook_lib",
    ],
)

py_test(
    name = "recipient_registry_test",
    srcs = ["recipient_registry_test.py"],
    deps = [
        "//backend/notification_management:recipient_registry",
    ],
)

py_test(
    name = "event_recorder_test",
    srcs = ["event_recorder_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/notification_management:event_recorder",
        "//backend/notification_management:recipient_registry",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)

py_test(
    name = "publish_on_commit_test",
    srcs = ["publish_on_commit_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/notification_management:event_recorder",
        "//backend/notification_management:publish_on_commit",
        "//backend/notification_management:recipient_registry",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)

py_test(
    name = "render_registry_test",
    srcs = ["render_registry_test.py"],
    deps = [
        "//backend/notification_management:render_registry",
    ],
)

py_test(
    name = "notification_event_email_service_test",
    srcs = ["notification_event_email_service_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/notification_management:notification_event_email_service",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)

py_test(
    name = "delivery_service_test",
    srcs = ["delivery_service_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/notification_management:delivery_service",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)

py_test(
    name = "delivery_controller_test",
    srcs = ["delivery_controller_test.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/notification_management:delivery_controller",
        "//backend/notification_management:delivery_service",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)
