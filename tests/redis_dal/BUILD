load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_redis_query_utils",
    srcs = ["test_redis_query_utils.py"],
    deps = [
        "//redis_dal:redis_query_utils",
        "@pypi//python_dateutil",
        "@pypi//redis",
    ],
)

py_test(
    name = "test_redis_api",
    srcs = ["test_redis_api.py"],
    deps = [
        "//redis_dal:redis_api",
        "//redis_dal:redis_query_utils",
        "//tools/global_handle_exception:exception_handler",
        "@pypi//flask",
        "@pypi//redis",
    ],
)
