load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@npm//:vitest/package_json.bzl", vitest_bin = "bin")

js_library(
    name = "frontend_unit_test_files",
    srcs = glob(["**/*test.js"]),
)

vitest_bin.vitest_test(
    name = "frontend_unit_tests",
    args = ["run"],
    chdir = package_name(),
    data = [
        ":frontend_unit_test_files",
        "//:npm_deps",
        "//frontend:all_srcs",
    ],
)
