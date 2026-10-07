load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "email_context_registry_test",
    srcs = ["email_context_registry_test.py"],
    deps = [
        "//backend/communication",
    ],
)

py_test(
    name = "email_conversation_service_test",
    srcs = ["email_conversation_service_test.py"],
    deps = [
        "//backend/common:communication_enums",
        "//backend/communication",
    ],
)

py_test(
    name = "email_templates_test",
    srcs = ["email_templates_test.py"],
    deps = [
        "//backend/communication",
    ],
)

py_test(
    name = "inbound_kind_test",
    srcs = ["inbound_kind_test.py"],
    deps = [
        "//backend/common:communication_enums",
        "//backend/communication",
    ],
)

py_test(
    name = "meeting_scheduling_service_test",
    srcs = ["meeting_scheduling_service_test.py"],
    deps = [
        "//backend/common:exceptions",
        "//backend/communication",
    ],
)

py_test(
    name = "notification_email_service_test",
    srcs = ["notification_email_service_test.py"],
    deps = [
        "//backend/communication",
    ],
)

py_test(
    name = "gmail_push_controller_test",
    srcs = ["gmail_push_controller_test.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/communication",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "gmail_push_service_test",
    srcs = ["gmail_push_service_test.py"],
    deps = [
        "//backend/communication",
    ],
)

py_test(
    name = "gmail_maintenance_service_test",
    srcs = ["gmail_maintenance_service_test.py"],
    deps = [
        "//backend/communication",
    ],
)

py_test(
    name = "gmail_sync_service_test",
    srcs = ["gmail_sync_service_test.py"],
    deps = [
        "//backend/common:exceptions",
        "//backend/communication",
    ],
)

py_test(
    name = "gmail_sync_controller_test",
    srcs = ["gmail_sync_controller_test.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:permissions",
        "//backend/communication",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "gmail_sync_service_db_test",
    srcs = ["gmail_sync_service_db_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/common:ops_enums",
        "//backend/communication",
        "//backend/entity:entities",
        "//backend/ops",
        "//backend/repository:repositories",
        "//tests/backend_test/repository_test:base_repository_test_lib",
        "@pypi//sqlalchemy",
    ],
)

py_test(
    name = "inbox_aliases_test",
    srcs = ["inbox_aliases_test.py"],
    deps = [
        "//backend/common:communication_enums",
        "//backend/communication",
    ],
)

py_test(
    name = "inbox_state_test",
    srcs = ["inbox_state_test.py"],
    deps = [
        "//backend/communication",
    ],
)
