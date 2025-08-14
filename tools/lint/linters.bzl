load("@aspect_rules_lint//lint:eslint.bzl", "lint_eslint_aspect")
load("@aspect_rules_lint//lint:ruff.bzl", "lint_ruff_aspect")

ruff = lint_ruff_aspect(
    binary = "@multitool//tools/ruff",
    configs = [
        Label("//:.ruff.toml"),
    ],
)

eslint = lint_eslint_aspect(
    binary = Label("//tools/lint:eslint"),
    # ESLint will resolve the configuration file by looking in the working directory first.
    # See https://eslint.org/docs/latest/use/configure/configuration-files#configuration-file-resolution
    # We must also include any other config files we expect eslint to be able to locate, e.g. tsconfigs
    configs = [
        Label("//:eslintrc"),
    ],
)
