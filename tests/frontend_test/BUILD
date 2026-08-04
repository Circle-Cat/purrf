load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@npm//:vitest/package_json.bzl", vitest_bin = "bin")

js_library(
    name = "vitest_config",
    srcs = [
        "setupTests.js",
        "vitest.config.mjs",
    ],
)

js_library(
    name = "frontend_unit_test_files",
    srcs = glob([
        "**/*test.js",
        "**/*test.jsx",
        "**/*.helper.js",
    ]),
)

_SHARD_COUNT = 10

[
    vitest_bin.vitest_test(
        name = "frontend_unit_tests_%d" % i,
        size = "large",
        args = [
            "run",
            "--reporter=verbose",
            "--shard=%d/%d" % (i, _SHARD_COUNT),
        ],
        chdir = package_name(),
        data = [
            ":frontend_unit_test_files",
            ":vitest_config",
            "//:npm_deps",
            "//frontend:all_srcs",
        ],
        flaky = True,
    )
    for i in range(
        1,
        _SHARD_COUNT + 1,
    )
]

test_suite(
    name = "frontend_unit_tests",
    tests = [":frontend_unit_tests_%d" % i for i in range(
        1,
        _SHARD_COUNT + 1,
    )],
)
