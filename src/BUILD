load("@rules_python//python:defs.bzl", "py_binary")

package(default_visibility = ["//visibility:public"])

py_binary(
    name = "purrf",
    srcs = ["app.py"],
    main = "app.py",
    deps = [
        "//src/common:error_handler",
        "@pypi//flask",
    ],
)
