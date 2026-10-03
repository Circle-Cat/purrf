load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "google_chat_processor_service",
    srcs = [
        "google_chat_processor_service.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:google_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "gerrit_processor_service",
    srcs = [
        "gerrit_processor_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "pubsub_push_service",
    srcs = [
        "pubsub_push_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "pubsub_push_controller",
    srcs = [
        "pubsub_push_controller.py",
    ],
    deps = [
        ":pubsub_push_service",
        "//backend/common:api_endpoints",
        "@pypi//fastapi",
    ],
)
