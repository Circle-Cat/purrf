load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "google_chat_message_store_test",
    srcs = ["google_chat_message_store_test.py"],
    deps = [
        "//backend/utils:google_chat_message_store",
    ],
)

py_test(
    name = "google_chat_utils_test",
    srcs = ["google_chat_utils_test.py"],
    deps = [
        "//backend/utils:google_chat_utils",
    ],
)

py_test(
    name = "microsoft_chat_message_store_test",
    srcs = ["microsoft_chat_message_store_test.py"],
    deps = [
        "//backend/utils:microsoft_chat_message_store",
    ],
)

py_test(
    name = "date_time_util_test",
    srcs = ["date_time_util_test.py"],
    deps = [
        "//backend/utils:date_time_util",
    ],
)

py_test(
    name = "retry_utils_test",
    srcs = [
        "retry_utils_test.py",
    ],
    deps = [
        "//backend/utils:retry_utils",
        "@pypi//tenacity",
    ],
)

py_test(
    name = "app_dependency_builder_test",
    srcs = ["app_dependency_builder_test.py"],
    deps = [
        "//backend/utils:app_dependency_builder",
    ],
)

py_test(
    name = "microsoft_chat_message_util_test",
    srcs = ["microsoft_chat_message_util_test.py"],
    deps = [
        "//backend/utils:microsoft_chat_message_util",
    ],
)
