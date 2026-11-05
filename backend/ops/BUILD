load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "ops",
    srcs = glob(["*.py"]),
    deps = [
        "//backend/common:ops_enums",
        "//backend/common:permissions",
        "//backend/entity:entities",
        "//backend/notification_management:event_recorder",
        "//backend/notification_management:recipient_registry",
        "//backend/notification_management:render_registry",
        "//backend/repository:repositories",
        "@pypi//sqlalchemy",
    ],
)
