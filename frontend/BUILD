load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@npm//:vite/package_json.bzl", vite_bin = "bin")

package(default_visibility = ["//visibility:public"])

js_library(
    name = "root_files",
    srcs = [
        "index.html",
    ],
)

js_library(
    name = "source_files",
    srcs = glob(["src/**"]),
)

js_library(
    name = "public_assets",
    srcs = glob(["public/**"]),
)

js_library(
    name = "vite_config",
    srcs = ["vite.config.mjs"],
)

js_library(
    name = "all_srcs",
    srcs = [
        ":public_assets",
        ":root_files",
        ":source_files",
        ":vite_config",
    ],
)

genrule(
    name = "gen_env",
    outs = [".env.production"],
    cmd = """
      echo "VITE_AUTH0_DOMAIN=$${VITE_AUTH0_DOMAIN:-}" >> $@
      echo "VITE_CF_ACCESS_TENANT_DOMAIN=$${VITE_CF_ACCESS_TENANT_DOMAIN:-}" >> $@
      echo "VITE_API_BASE_URL=$${VITE_API_BASE_URL:-}" > $@
      echo "VITE_AUTH0_CLIENT_ID=$${VITE_AUTH0_CLIENT_ID:-}" >> $@
    """,
)

vite_bin.vite(
    name = "dist",
    srcs = [
        ":all_srcs",
        ":gen_env",
        "//:npm_deps",
    ],
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
        "vite.config.mjs",
        ":dist",
    ],
)

vite_bin.vite_binary(
    name = "dev_server",
    chdir = package_name(),
    data = [
        ":all_srcs",
        "//:npm_deps",
    ],
    # Under ibazel, let vite hot-reload changed files rather than restart it
    tags = ["ibazel_notify_changes"],
)

# Build: Use bazel build //frontend:dist to generate production-ready static assets.
# Development: Use bazel run //frontend:dev_server (with ibazel) for rapid iterative development.
# Preview: Use bazel run //frontend:vite_preview to locally preview the production build.
