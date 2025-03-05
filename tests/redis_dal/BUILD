load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_redis_client_factory",
    srcs = ["test_redis_client_factory.py"],
    deps = [
        "//redis_dal:redis_client_factory",
        "@pypi//redis",
    ],
)

py_test(
    name = "test_redis_utils",
    srcs = ["test_redis_utils.py"],
    deps = [
        "//redis_dal:redis_utils",
    ],
)
