load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = [
    "//purrf/google:__pkg__",
    "//tests/google:__pkg__",
])

py_library(
    name = "authentication_utils",
    srcs = [
        "authentication_utils.py",
        "constants.py",
    ],
    deps = [
        "//tools/log",
        "@pypi//google_api_python_client",
        "@pypi//google_auth_oauthlib",
    ],
)

py_library(
    name = "chat_utils",
    srcs = [
        "chat_utils.py",
        "constants.py",
    ],
    deps = [
        "//tools/log",
    ],
)
