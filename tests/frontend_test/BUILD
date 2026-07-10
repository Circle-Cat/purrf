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

# One vitest process running all ~1500 tests grows its worker-teardown time
# as the suite grows, occasionally exceeding vitest.config.mjs's
# teardownTimeout under CI load (bazel reports this as a full-target
# TIMEOUT even though every test passed). Sharding via vitest's built-in
# --shard flag keeps each process's module graph small enough to close
# reliably, and lets bazel run shards in parallel.
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
