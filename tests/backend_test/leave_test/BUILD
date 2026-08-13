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
        "//backend/leave:employment_sync_service",
    ],
)
