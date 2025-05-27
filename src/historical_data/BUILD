load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "google_calendar_history_fetcher",
    srcs = [
        "google_calendar_history_fetcher.py",
    ],
    deps = [
        "//src/common:google_client",
        "//src/common:logger",
        "@pypi//tenacity",
    ],
)
