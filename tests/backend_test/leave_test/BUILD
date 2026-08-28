load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "employment_profile_test",
    srcs = ["employment_profile_test.py"],
    deps = [
        "//backend/leave:employment_profile",
    ],
)

py_test(
    name = "coverage_report_test",
    srcs = ["coverage_report_test.py"],
    deps = [
        "//backend/leave:coverage_report",
    ],
)

py_test(
    name = "employment_sync_service_test",
    srcs = ["employment_sync_service_test.py"],
    deps = [
        "//backend/common:leave_enums",
        "//backend/leave:employment_sync_service",
        "//backend/leave:leave_participants",
    ],
)

py_test(
    name = "leave_calendar_segments_test",
    srcs = ["leave_calendar_segments_test.py"],
    deps = [
        "//backend/leave:leave_calendar_segments",
    ],
)

py_test(
    name = "leave_policy_test",
    srcs = ["leave_policy_test.py"],
    deps = [
        "//backend/leave:leave_policy",
    ],
)

py_test(
    name = "leave_calendar_service_test",
    srcs = ["leave_calendar_service_test.py"],
    deps = [
        "//backend/leave:leave_calendar_service",
    ],
)

py_test(
    name = "leave_clock_test",
    srcs = ["leave_clock_test.py"],
    deps = [
        "//backend/leave:leave_clock",
    ],
)

py_test(
    name = "leave_calendar_controller_test",
    srcs = ["leave_calendar_controller_test.py"],
    deps = [
        "//backend/leave:leave_calendar_controller",
    ],
)

py_test(
    name = "leave_accrual_test",
    srcs = ["leave_accrual_test.py"],
    deps = [
        "//backend/leave:leave_accrual",
        "//backend/leave:leave_clock",
    ],
)

py_test(
    name = "leave_adjustment_service_test",
    srcs = ["leave_adjustment_service_test.py"],
    deps = [
        "//backend/common:leave_enums",
        "//backend/leave:leave_adjustment_service",
    ],
)

py_test(
    name = "leave_admin_controller_test",
    srcs = ["leave_admin_controller_test.py"],
    deps = [
        "//backend/leave:leave_admin_controller",
    ],
)

py_test(
    name = "leave_participants_test",
    srcs = ["leave_participants_test.py"],
    deps = [
        "//backend/leave:leave_participants",
    ],
)

py_test(
    name = "leave_engine_service_test",
    srcs = ["leave_engine_service_test.py"],
    deps = [
        "//backend/common:leave_enums",
        "//backend/leave:leave_engine_service",
    ],
)

py_test(
    name = "leave_job_controller_test",
    srcs = ["leave_job_controller_test.py"],
    deps = [
        "//backend/leave:leave_job_controller",
    ],
)

py_test(
    name = "leave_workdays_test",
    srcs = ["leave_workdays_test.py"],
    deps = [
        "//backend/common:leave_enums",
        "//backend/leave:leave_workdays",
    ],
)

py_test(
    name = "leave_request_service_test",
    srcs = ["leave_request_service_test.py"],
    deps = [
        "//backend/common:leave_enums",
        "//backend/entity:entities",
        "//backend/leave:leave_request_service",
    ],
)

py_test(
    name = "leave_request_controller_test",
    srcs = ["leave_request_controller_test.py"],
    deps = [
        "//backend/common:leave_enums",
        "//backend/leave:leave_request_controller",
    ],
)
