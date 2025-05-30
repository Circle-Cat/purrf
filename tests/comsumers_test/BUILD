load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "pubsub_puller_test",
    srcs = ["pubsub_puller_test.py"],
    deps = [
        "//src/consumers:pubsub_puller",
    ],
)

py_test(
    name = "pubsub_pull_manager_test",
    srcs = ["pubsub_pull_manager_test.py"],
    deps = [
        "//src/consumers:pubsub_pull_manager",
    ],
)
