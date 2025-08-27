load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "google_chat_message_store",
    srcs = [
        "google_chat_message_store.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:redis_client",
    ],
)

py_library(
    name = "google_chat_utils",
    srcs = [
        "google_chat_utils.py",
    ],
    deps = [
        "//backend/common:google_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_chat_message_store",
    srcs = [
        "microsoft_chat_message_store.py",
    ],
    deps = [
        "//backend/common:constants",
        "//backend/common:microsoft_client",
        "//backend/common:redis_client",
        "@pypi//tenacity",
    ],
)

py_library(
    name = "date_time_util",
    srcs = [
        "date_time_util.py",
    ],
    deps = [
        "//backend/common:constants",
        "@pypi//python_dateutil",
    ],
)

py_library(
    name = "retry_utils",
    srcs = [
        "retry_utils.py",
    ],
    deps = [
        "@pypi//tenacity",
    ],
)

py_library(
    name = "microsoft_chat_message_util",
    srcs = [
        "microsoft_chat_message_util.py",
    ],
    deps = [
        "//backend/common:constants",
    ],
)

py_library(
    name = "app_dependency_builder",
    srcs = [
        "app_dependency_builder.py",
    ],
    deps = [
        ":date_time_util",
        ":microsoft_chat_message_util",
        ":retry_utils",
        "//backend/common:logger",
        "//backend/common:microsoft_graph_service_client",
        "//backend/common:redis_client",
        "//backend/consumers:consumer_controller",
        "//backend/consumers:microsoft_message_processor_service",
        "//backend/consumers:pubsub_puller",
        "//backend/consumers:pubsub_puller_factory",
        "//backend/frontend_service:frontend_controller",
        "//backend/frontend_service:ldap_service",
        "//backend/historical_data:historical_controller",
        "//backend/historical_data:microsoft_member_sync_service",
        "//backend/notification_management:microsoft_chat_subscription_service",
        "//backend/notification_management:notification_controller",
        "//backend/service:microsoft_service",
    ],
)
