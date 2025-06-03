load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "frontend_api_test",
    srcs = ["frontend_api_test.py"],
    deps = [
        "//src/frontend_service:frontend_api",
    ],
)

py_test(
    name = "ldap_loader_test",
    srcs = ["ldap_loader_test.py"],
    deps = [
        "//src/frontend_service:ldap_loader",
    ],
)
