load("@rules_python//python:defs.bzl", "py_binary")
load("@rules_python//python/entry_points:py_console_script_binary.bzl", "py_console_script_binary")

package(default_visibility = ["//visibility:public"])

py_binary(
    name = "purrf",
    srcs = ["app.py"],
    main = "app.py",
    deps = [
        "//src/common:error_handler",
        "//src/consumers:consumer_api",
        "//src/frontend_service:frontend_api",
        "//src/historical_data:historical_api",
        "//src/notification_management:notification_api",
        "@pypi//flask",
    ],
)

py_console_script_binary(
    name = "uvicorn",
    pkg = "@pypi//uvicorn",
    deps = [":purrf"],
)
