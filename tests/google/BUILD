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
        "//google:chat_utils",
    ],
)
