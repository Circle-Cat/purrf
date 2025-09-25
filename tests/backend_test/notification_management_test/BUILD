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
        "//backend/notification_management:notification_controller",
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
