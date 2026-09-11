load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "user_identity_service",
    srcs = ["user_identity_service.py"],
    deps = [
        "//backend/common:mentorship_enums",
        "//backend/common:trusted_connections",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/user_identity:internal_lifecycle",
    ],
)

py_library(
    name = "internal_lifecycle",
    srcs = ["internal_lifecycle.py"],
    deps = [
        "//backend/common:permissions",
    ],
)

py_library(
    name = "internal_onboarding_training",
    srcs = ["internal_onboarding_training.py"],
    deps = [
        "//backend/common:constants",
        "//backend/common:mentorship_enums",
    ],
)

py_library(
    name = "user_recipient_resolvers",
    srcs = ["user_recipient_resolvers.py"],
    deps = [
        "//backend/common:user_enums",
        "//backend/entity:entities",
        "//backend/notification_management:recipient_registry",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)

py_library(
    name = "notification_renderers",
    srcs = ["notification_renderers.py"],
    deps = [
        "//backend/common:name_utils",
        "//backend/common:user_enums",
        "//backend/entity:entities",
        "//backend/notification_management:render_registry",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)
