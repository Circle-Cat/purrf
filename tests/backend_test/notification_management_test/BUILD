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
    name = "gerrit_watcher_test",
    srcs = ["gerrit_watcher_test.py"],
    deps = [
        "//backend/notification_management:gerrit_watcher",
    ],
)
