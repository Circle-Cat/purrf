load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@aspect_rules_lint//format:defs.bzl", "format_multirun")
load("@npm//:prettier/package_json.bzl", prettier = "bin")

package(default_visibility = ["format_access_file_group"])

package_group(
    name = "format_access_file_group",
    packages = [
        "//",
    ],
)

js_library(
    name = "prettierrc",
    srcs = ["prettier.config.cjs"],
    deps = [
        "//:node_modules/@prettier/plugin-xml",
        "//:node_modules/prettier-plugin-gherkin",
        "//:node_modules/prettier-plugin-sql",
    ],
)

prettier.prettier_binary(
    name = "prettier",
    # Include this js_library and its dependencies in the runfiles (runtime dependencies)
    data = [
        ":prettierrc",
    ],
    # Allow the binary to be run outside bazel
    env = {"BAZEL_BINDIR": "."},
    fixed_args = [
        "--config=\"$$JS_BINARY__RUNFILES\"/$(rlocationpath :prettierrc)",
        "--log-level=warn",
    ],
)

format_multirun(
    name = "format",
    javascript = ":prettier",
    python = "@aspect_rules_lint//format:ruff",
    starlark = "@buildifier_prebuilt//:buildifier",
)
