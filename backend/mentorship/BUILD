load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "mentorship",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:api_endpoints",
        "//backend/common:constants",
        "//backend/common:exceptions",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:identity_type",
        "//backend/common:mentorship_enums",
        "//backend/common:name_utils",
        "//backend/common:permissions",
        "//backend/common:recruiting_enums",
        "//backend/common:wall_clock",
        "//backend/communication",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/notification_management:event_recorder",
        "//backend/notification_management:recipient_registry",
        "//backend/notification_management:render_registry",
        "//backend/repository:repositories",
        "//backend/service:launchdarkly_service",
        "//backend/utils:date_time_util",
        "//backend/utils:permission_decorators",
        "@pypi//intervaltree",
        "@pypi//python_dateutil",
        "@pypi//sortedcontainers",
        "@pypi//sqlalchemy",
    ],
)
