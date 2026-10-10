load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "block_service_request_test",
    srcs = ["block_service_request_test.py"],
    deps = [
        "//backend/admin:block_service",
        "//backend/admin:block_user_handler",
        "//backend/approval:approval_service",
        "//backend/common:approval_enums",
        "//backend/common:exceptions",
        "//backend/common:permissions",
        "//backend/common:user_enums",
        "//backend/entity:entities",
        "@pypi//sqlalchemy",
    ],
)

py_test(
    name = "block_service_apply_test",
    srcs = ["block_service_apply_test.py"],
    deps = [
        "//backend/admin:block_service",
        "//backend/common:exceptions",
        "//backend/common:recruiting_enums",
        "//backend/common:user_enums",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "user_account_service_test",
    srcs = ["user_account_service_test.py"],
    deps = [
        "//backend/admin:block_service",
        "//backend/admin:user_account_service",
        "//backend/common:approval_enums",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "permission_admin_service_test",
    srcs = ["permission_admin_service_test.py"],
    deps = [
        "//backend/admin:permission_admin_service",
        "//backend/common:permission_descriptions",
        "//backend/common:permissions",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "permission_admin_controller_test",
    srcs = ["permission_admin_controller_test.py"],
    deps = [
        "//backend/admin:permission_admin_controller",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_error_handler",
        "//backend/common:permissions",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "user_account_controller_test",
    srcs = ["user_account_controller_test.py"],
    deps = [
        "//backend/admin:user_account_controller",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_error_handler",
        "//backend/common:permissions",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "block_controller_test",
    srcs = ["block_controller_test.py"],
    deps = [
        "//backend/admin:block_controller",
        "//backend/common:api_endpoints",
        "//backend/common:exceptions",
        "//backend/common:fast_api_error_handler",
        "//backend/common:permissions",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)

py_test(
    name = "block_user_handler_test",
    srcs = ["block_user_handler_test.py"],
    deps = [
        "//backend/admin:block_user_handler",
        "//backend/common:user_enums",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "block_request_flow_test",
    srcs = ["block_request_flow_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/admin:block_service",
        "//backend/admin:block_user_handler",
        "//backend/approval:approval_service",
        "//backend/common:approval_enums",
        "//backend/common:exceptions",
        "//backend/common:mentorship_enums",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "//backend/user_identity:notification_renderers",
        "//backend/user_identity:user_recipient_resolvers",
        "//tests/backend_test/repository_test:base_repository_test_lib",
        "@pypi//sqlalchemy",
    ],
)

py_test(
    name = "block_ends_mentorship_flow_test",
    srcs = ["block_ends_mentorship_flow_test.py"],
    env_inherit = ["DATABASE_URL"],
    deps = [
        "//backend/admin:block_service",
        "//backend/admin:block_user_handler",
        "//backend/approval:approval_service",
        "//backend/common:exceptions",
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/mentorship",
        "//backend/repository:repositories",
        "//backend/user_identity:notification_renderers",
        "//backend/user_identity:user_recipient_resolvers",
        "//tests/backend_test/repository_test:base_repository_test_lib",
        "@pypi//sqlalchemy",
    ],
)
