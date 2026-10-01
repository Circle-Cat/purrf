load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "ops_alert_service_test",
    srcs = ["ops_alert_service_test.py"],
    deps = ["//backend/ops"],
)

py_test(
    name = "recipient_resolvers_test",
    srcs = ["recipient_resolvers_test.py"],
    deps = [
        "//backend/common:ops_enums",
        "//backend/notification_management:recipient_registry",
        "//backend/ops",
        "//backend/repository:repositories",
    ],
)

py_test(
    name = "notification_renderers_test",
    srcs = ["notification_renderers_test.py"],
    deps = [
        "//backend/common:ops_enums",
        "//backend/entity:entities",
        "//backend/notification_management:recipient_registry",
        "//backend/notification_management:render_registry",
        "//backend/ops",
    ],
)
