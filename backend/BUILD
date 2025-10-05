load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load("@rules_python//python/entry_points:py_console_script_binary.bzl", "py_console_script_binary")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "app",
    srcs = [
        "app.py",
    ],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/common:error_handler",
        "@pypi//flask",
    ],
)

py_binary(
    name = "dev_runner",
    srcs = ["dev_runner.py"],
    main = "dev_runner.py",
    deps = [
        ":app",
        "//backend/utils:app_dependency_builder",
    ],
)

py_binary(
    name = "prod_runner",
    srcs = ["prod_runner.py"],
    main = "prod_runner.py",
    deps = [
        ":app",
        "//backend/utils:app_dependency_builder",
    ],
)

py_console_script_binary(
    name = "uvicorn",
    pkg = "@pypi//uvicorn",
    deps = [":prod_runner"],
)
