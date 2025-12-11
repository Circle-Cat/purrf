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
        "//backend/common:api_endpoints",
        "//backend/common:constants",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:user_role",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
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
