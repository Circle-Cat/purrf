load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "microsoft_chat_subscription_service",
    srcs = [
        "microsoft_chat_subscription_service.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "notification_controller",
    srcs = [
        "notification_controller.py",
    ],
    deps = [
        "//backend/common:api_response_wrapper",
        "//backend/common:constants",
        "//backend/notification_management:gerrit_subscription_service",
        "//backend/notification_management:google_chat_subscription_service",
        "@pypi//flask",
    ],
)

py_library(
    name = "gerrit_subscription_service",
    srcs = [
        "gerrit_subscription_service.py",
    ],
    deps = [
        "//backend/common:environment_constants",
    ],
)

py_library(
    name = "google_chat_subscription_service",
    srcs = [
        "google_chat_subscription_service.py",
    ],
    deps = [
        "@pypi//tenacity",
    ],
)
