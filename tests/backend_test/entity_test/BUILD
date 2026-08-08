load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "application_entity_test",
    srcs = ["application_entity_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "application_assignment_entity_test",
    srcs = ["application_assignment_entity_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "evaluation_entity_test",
    srcs = ["evaluation_entity_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "event_entity_test",
    srcs = ["event_entity_test.py"],
    deps = ["//backend/entity:entities"],
)

py_test(
    name = "notification_entity_test",
    srcs = ["notification_entity_test.py"],
    deps = [
        "//backend/common:recruiting_enums",
        "//backend/entity:entities",
    ],
)
