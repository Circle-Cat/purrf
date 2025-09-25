load("@rules_python//python:defs.bzl", "py_binary", "py_library")

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

py_library(
    name = "gerrit_webhook_lib",
    srcs = ["gerrit_webhook_lib.py"],
    deps = [
        ":gerrit_subscription_service",
        "//backend/common:environment_constants",
        "//backend/common:gerrit_client",
        "//backend/common:logger",
    ],
)

py_binary(
    name = "register_gerrit_webhook",
    srcs = ["register_gerrit_webhook.py"],
    main = "register_gerrit_webhook.py",
    deps = [
        ":gerrit_webhook_lib",
    ],
)
