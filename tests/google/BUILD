load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_authentication_utils",
    srcs = ["test_authentication_utils.py"],
    deps = [
        "//google:authentication_utils",
        "@pypi//google_auth_oauthlib",
    ],
)

py_test(
    name = "test_chat_utils",
    srcs = ["test_chat_utils.py"],
    deps = [
        "//google:authentication_utils",
        "//google:chat_utils",
    ],
)

py_test(
    name = "test_fetch_history_chat_message",
    srcs = ["test_fetch_history_chat_message.py"],
    deps = [
        "//google:fetch_history_chat_message",
    ],
)
