load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "job_service_test",
    srcs = ["job_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "recruiting_mapper_test",
    srcs = ["recruiting_mapper_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "recruiting_controller_test",
    srcs = ["recruiting_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "cooldown_test",
    srcs = ["cooldown_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/recruiting",
    ],
)

py_test(
    name = "application_stages_vector_test",
    srcs = ["application_stages_vector_test.py"],
    data = ["//tests/shared:application_stages_vector"],
    deps = [
        "//backend/common:recruiting_enums",
    ],
)

py_test(
    name = "form_visibility_test",
    srcs = ["form_visibility_test.py"],
    data = ["//tests/shared:form_visibility_vectors"],
    deps = [
        "//backend/recruiting",
    ],
)

py_test(
    name = "screen_rules_test",
    srcs = ["screen_rules_test.py"],
    deps = [
        "//backend/recruiting",
    ],
)

py_test(
    name = "stage_machine_test",
    srcs = ["stage_machine_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/recruiting",
    ],
)

py_test(
    name = "evaluation_rubric_test",
    srcs = ["evaluation_rubric_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/recruiting",
    ],
)

py_test(
    name = "resume_storage_test",
    srcs = ["resume_storage_test.py"],
    deps = [
        "//backend/recruiting",
        "@pypi//google_api_core",
        "@pypi//google_cloud_storage",
    ],
)

py_test(
    name = "application_service_test",
    srcs = ["application_service_test.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/mentorship",
        "//backend/recruiting",
    ],
)

py_test(
    name = "application_controller_test",
    srcs = ["application_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
        "@pypi//python_multipart",
    ],
)

py_test(
    name = "pipeline_owners_test",
    srcs = ["pipeline_owners_test.py"],
    deps = [
        "//backend/recruiting",
    ],
)

py_test(
    name = "board_service_test",
    srcs = ["board_service_test.py"],
    deps = [
        "//backend/common:communication_enums",
        "//backend/common:permissions",
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/mentorship",
        "//backend/recruiting",
    ],
)

py_test(
    name = "evaluation_service_test",
    srcs = ["evaluation_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "board_controller_test",
    srcs = ["board_controller_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "blacklist_service_test",
    srcs = ["blacklist_service_test.py"],
    deps = [
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "blacklist_controller_test",
    srcs = ["blacklist_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "evaluation_controller_test",
    srcs = ["evaluation_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "audit_service_test",
    srcs = ["audit_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
        "//backend/recruiting",
    ],
)

py_test(
    name = "audit_controller_test",
    srcs = ["audit_controller_test.py"],
    deps = [
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "notification_service_test",
    srcs = ["notification_service_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
        "//backend/repository:repositories",
    ],
)

py_test(
    name = "notification_controller_test",
    srcs = ["notification_controller_test.py"],
    deps = [
        "//backend/dto",
        "//backend/recruiting",
    ],
)

py_test(
    name = "email_sync_service_test",
    srcs = ["email_sync_service_test.py"],
    deps = [
        "//backend/common:communication_enums",
        "//backend/recruiting",
    ],
)

py_test(
    name = "interview_scheduling_service_test",
    srcs = ["interview_scheduling_service_test.py"],
    deps = [
        "//backend/common:exceptions",
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/recruiting",
        "//backend/repository:repositories",
    ],
)

py_test(
    name = "notification_email_copy_test",
    srcs = ["notification_email_copy_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/dto",
        "//backend/recruiting",
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
        "//backend/notification_management:recipient_registry",
        "//backend/recruiting",
        "//tests/backend_test/repository_test:base_repository_test_lib",
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
        "//backend/notification_management:recipient_registry",
        "//backend/notification_management:render_registry",
        "//backend/recruiting",
        "//tests/backend_test/repository_test:base_repository_test_lib",
    ],
)
