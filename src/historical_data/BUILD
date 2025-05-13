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

py_library(
    name = "microsoft_ldap_fetcher",
    srcs = [
        "microsoft_ldap_fetcher.py",
    ],
    deps = [
        "//src/common:microsoft_client",
        "//src/common:redis_client",
    ],
)

py_library(
    name = "historical_api",
    srcs = ["historical_api.py"],
    deps = [
        "//src/historical_data:microsoft_ldap_fetcher",
        "@pypi//flask",
    ],
)
