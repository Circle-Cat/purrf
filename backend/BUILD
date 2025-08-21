load("@rules_python//python:defs.bzl", "py_binary")
load("@rules_python//python/entry_points:py_console_script_binary.bzl", "py_console_script_binary")

package(default_visibility = ["//visibility:public"])

config_setting(
    name = "run_test",
    values = {"define": "run_test=true"},
)

py_binary(
    name = "purrf",
    srcs = ["app.py"],
    main = "app.py",
    deps = select({
        "//backend:run_test": [
            "//backend/common:error_handler",
            "//backend/common:api_response_wrapper",
            "@pypi//flask",
            # TODO: After migration, remove these dependencies from the test section:
            "//backend/consumers:consumer_controller",
            "//backend/frontend_service:frontend_api",
            "//backend/historical_data:historical_controller",
            "//backend/notification_management:notification_controller",
        ],
        "//conditions:default": [
            "//backend/common:api_response_wrapper",
            "//backend/common:error_handler",
            "//backend/consumers:consumer_controller",
            "//backend/frontend_service:frontend_api",
            "//backend/historical_data:historical_controller",
            "//backend/notification_management:notification_controller",
            "//backend/utils:app_dependency_builder",
            "@pypi//flask",
        ],
    }),
)

py_console_script_binary(
    name = "uvicorn",
    pkg = "@pypi//uvicorn",
    deps = [":purrf"],
)
