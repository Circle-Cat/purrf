load("@npm//:eslint/package_json.bzl", eslint_bin = "bin")

package(default_visibility = ["lint_access_file_group"])

package_group(
    name = "lint_access_file_group",
    packages = [
        "//tools/lint",
    ],
)

eslint_bin.eslint_binary(
    name = "eslint",
    data = [
        "//:eslintrc",
    ],
)
