load("@npm//:defs.bzl", "npm_link_all_packages", "npm_link_targets")
load("@npm//frontend:vite/package_json.bzl", vite_bin = "bin")

package(default_visibility = ["//visibility:public"])

npm_link_all_packages(name = "node_modules")

filegroup(
    name = "vite_config",
    srcs = ["vite.config.js"],
)

filegroup(
    name = "root_files",
    srcs = [
        "index.html",
        "package.json",
    ],
)

filegroup(
    name = "source_files",
    srcs = glob(["src/**"]),
)

filegroup(
    name = "public_assets",
    srcs = glob(["public/**"]),
)

filegroup(
    name = "npm_deps",
    srcs = npm_link_targets(),
)

filegroup(
    name = "all_srcs",
    srcs = [
        ":npm_deps",
        ":public_assets",
        ":root_files",
        ":source_files",
        ":vite_config",
    ],
)

vite_bin.vite(
    name = "dist",
    srcs = [":all_srcs"],
    args = [
        "build",
        "--mode=production",
    ],
    chdir = package_name(),
    out_dirs = ["dist"],
)

vite_bin.vite_binary(
    name = "vite_preview",
    args = [
        "preview",
        "--outDir",
        "dist",
    ],
    chdir = package_name(),
    data = [
        "vite.config.js",
        ":dist",
    ],
)

vite_bin.vite_binary(
    name = "dev_server",
    chdir = package_name(),
    data = [":all_srcs"],
    # Under ibazel, let vite hot-reload changed files rather than restart it
    tags = ["ibazel_notify_changes"],
)

# Build: Use bazel build //frontend:dist to generate production-ready static assets.
# Development: Use bazel run //frontend:dev_server (with ibazel) for rapid iterative development.
# Preview: Use bazel run //frontend:vite_preview to locally preview the production build.
