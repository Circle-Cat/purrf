load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_test(
    name = "mentorship_mapper_test",
    srcs = ["mentorship_mapper_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "mentorship_controller_test",
    srcs = ["mentorship_controller_test.py"],
    deps = [
        "//backend/mentorship",
        "@pypi//httpx",
    ],
)

py_test(
    name = "rounds_service_test",
    srcs = ["rounds_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "participation_service_test",
    srcs = ["participation_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "registration_service_test",
    srcs = ["registration_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "meeting_service_test",
    srcs = ["meeting_service_test.py"],
    deps = ["//backend/mentorship"],
)

py_test(
    name = "meet_attendance_service_test",
    srcs = ["meet_attendance_service_test.py"],
    deps = ["//backend/mentorship"],
)
