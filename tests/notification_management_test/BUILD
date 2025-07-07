load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "microsoft_chat_watcher_test",
    srcs = ["microsoft_chat_watcher_test.py"],
    deps = [
        "//src/notification_management:microsoft_chat_watcher",
    ],
)

py_test(
    name = "notification_api_test",
    srcs = ["notification_api_test.py"],
    deps = [
        "//src/notification_management:notification_api",
    ],
)

py_test(
    name = "google_chat_watcher_test",
    srcs = ["google_chat_watcher_test.py"],
    deps = [
        "//src/notification_management:google_chat_watcher",
    ],
)
