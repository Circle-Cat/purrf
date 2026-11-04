load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@npm//:vitest/package_json.bzl", vitest_bin = "bin")

js_library(
    name = "router_sources",
    srcs = glob([
        "src/*.js",
        "vitest.config.mjs",
        "vitest.setup.js",
    ]),
)

vitest_bin.vitest_test(
    name = "apply_router_tests",
    args = ["run"],
    chdir = package_name(),
    data = [
        ":router_sources",
        "//:npm_deps",
    ],
)
