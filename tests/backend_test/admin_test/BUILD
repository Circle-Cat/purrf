load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "permission_admin_service_test",
    srcs = ["permission_admin_service_test.py"],
    deps = [
        "//backend/admin:permission_admin_service",
        "//backend/common:permissions",
        "//backend/entity:entities",
    ],
)

py_test(
    name = "permission_admin_controller_test",
    srcs = ["permission_admin_controller_test.py"],
    deps = [
        "//backend/admin:permission_admin_controller",
        "//backend/common:api_endpoints",
        "//backend/common:fast_api_error_handler",
        "//backend/common:permissions",
        "//backend/dto",
        "@pypi//fastapi",
        "@pypi//httpx",
    ],
)
