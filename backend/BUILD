load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load("@rules_python//python/entry_points:py_console_script_binary.bzl", "py_console_script_binary")

package(default_visibility = ["//visibility:public"])

py_binary(
    name = "fast_app_dev_runner",
    srcs = ["fast_app_dev_runner.py"],
    main = "fast_app_dev_runner.py",
    deps = [
        "//backend/utils:app_dependency_builder",
        "@pypi//uvicorn",
    ],
)

py_binary(
    name = "prod_runner",
    srcs = ["prod_runner.py"],
    main = "prod_runner.py",
    deps = [
        "//backend/utils:app_dependency_builder",
    ],
)

py_console_script_binary(
    name = "uvicorn",
    pkg = "@pypi//uvicorn",
    deps = [":prod_runner"],
)
