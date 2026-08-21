load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "employment_profile",
    srcs = ["employment_profile.py"],
)

py_library(
    name = "coverage_report",
    srcs = ["coverage_report.py"],
    deps = [
        ":employment_profile",
    ],
)

py_library(
    name = "employment_sync_service",
    srcs = ["employment_sync_service.py"],
    deps = [
        ":coverage_report",
        ":employment_profile",
        "//backend/common:constants",
    ],
)

py_library(
    name = "leave_calendar_segments",
    srcs = ["leave_calendar_segments.py"],
    deps = [
        "//backend/dto",
        "//backend/entity:entities",
    ],
)

py_library(
    name = "leave_policy",
    srcs = ["leave_policy.py"],
    deps = [
        ":employment_profile",
        "//backend/dto",
    ],
)

py_library(
    name = "leave_calendar_service",
    srcs = ["leave_calendar_service.py"],
    deps = [
        ":leave_calendar_segments",
        ":leave_clock",
        ":leave_policy",
        "//backend/dto",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)

py_library(
    name = "leave_clock",
    srcs = ["leave_clock.py"],
    deps = [
        ":employment_profile",
    ],
)

py_library(
    name = "leave_calendar_controller",
    srcs = ["leave_calendar_controller.py"],
    deps = [
        ":leave_calendar_service",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)

py_library(
    name = "leave_accrual",
    srcs = ["leave_accrual.py"],
)

py_library(
    name = "leave_adjustment_service",
    srcs = ["leave_adjustment_service.py"],
    deps = [
        ":leave_clock",
        "//backend/common:leave_enums",
        "//backend/dto",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)

py_library(
    name = "leave_admin_controller",
    srcs = ["leave_admin_controller.py"],
    deps = [
        ":leave_adjustment_service",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:permissions",
        "//backend/dto",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)

py_library(
    name = "leave_participants",
    srcs = ["leave_participants.py"],
    deps = [
        "//backend/common:constants",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)

py_library(
    name = "leave_engine_service",
    srcs = ["leave_engine_service.py"],
    deps = [
        ":leave_accrual",
        ":leave_clock",
        ":leave_participants",
        ":leave_policy",
        "//backend/common:leave_enums",
        "//backend/entity:entities",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)

py_library(
    name = "leave_job_controller",
    srcs = ["leave_job_controller.py"],
    deps = [
        ":leave_engine_service",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_response_wrapper",
        "//backend/common:permissions",
        "//backend/utils:permission_decorators",
        "@pypi//fastapi",
    ],
)
