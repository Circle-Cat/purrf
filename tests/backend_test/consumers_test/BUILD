load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "google_chat_processor_service_test",
    srcs = ["google_chat_processor_service_test.py"],
    deps = [
        "//backend/consumers:google_chat_processor_service",
    ],
)

py_test(
    name = "gerrit_processor_service_test",
    srcs = ["gerrit_processor_service_test.py"],
    deps = [
        "//backend/consumers:gerrit_processor_service",
    ],
)

py_test(
    name = "pubsub_push_service_test",
    srcs = ["pubsub_push_service_test.py"],
    deps = [
        "//backend/common:constants",
        "//backend/consumers:pubsub_push_service",
    ],
)

py_test(
    name = "pubsub_push_controller_test",
    srcs = ["pubsub_push_controller_test.py"],
    deps = [
        "//backend/common:api_endpoints",
        "//backend/consumers:pubsub_push_controller",
        "//backend/consumers:pubsub_push_service",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)
