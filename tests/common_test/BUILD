load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "logger_test",
    srcs = ["logger_test.py"],
    deps = [
        "//src/common:logger",
    ],
)

py_test(
    name = "google_client_test",
    srcs = ["google_client_test.py"],
    deps = [
        "//src/common:google_client",
        "@pypi//google_api_python_client",
        "@pypi//google_auth_oauthlib",
        "@pypi//google_cloud_pubsub",
    ],
)
