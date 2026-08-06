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

# Entry document and config for the standalone prototype bundle. Kept out of
# :all_srcs so the normal app build graph is untouched.
js_library(
    name = "prototype_files",
    srcs = [
        "prototype.html",
        "vite.config.pages.mjs",
    ],
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
      echo "VITE_AUTH0_DOMAIN=$${VITE_AUTH0_DOMAIN:-}" > $@
      echo "VITE_CF_ACCESS_TENANT_DOMAIN=$${VITE_CF_ACCESS_TENANT_DOMAIN:-}" >> $@
      echo "VITE_API_BASE_URL=$${VITE_API_BASE_URL:-}" >> $@
      echo "VITE_AUTH0_CLIENT_ID=$${VITE_AUTH0_CLIENT_ID:-}" >> $@
      echo "VITE_LAUNCHDARKLY_CLIENT_ID=$${VITE_LAUNCHDARKLY_CLIENT_ID:-}" >> $@
      echo "VITE_DEPLOY_ENV=$${VITE_DEPLOY_ENV:-}" >> $@
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

# Dev server for the standalone prototypes. Serves prototype.html, whose entry
# mounts the prototypes bare — no Auth0, no LaunchDarkly, no router, no API — so
# it runs with nothing else up. This is the only way to view the prototypes
# locally without a backend; :dev_server boots the full app, which authenticates.
#
#   bazel run //frontend:prototype_dev_server
#   open http://localhost:5273/prototype.html#leave
#
# Pinned to 5273 with --strictPort, deliberately. :dev_server owns 5173, and
# vite's default behaviour when a port is taken is to slide silently to the next
# one — which lands you on whatever else is already serving 5173 and looks like
# the prototype is broken. Failing loudly is the whole point of strictPort here.
# Static bundle of the prototypes — the same artifact GitHub Pages serves.
# Plain HTML/JS/CSS with relative asset URLs, so any static file server can
# host it and no Node is needed at serve time:
#
#   bazel build //frontend:prototype_dist
#   python3 -m http.server -d bazel-bin/frontend/dist-pages 8080
#   open http://localhost:8080/prototype.html#leave
vite_bin.vite(
    name = "prototype_dist",
    srcs = [
        ":all_srcs",
        ":prototype_files",
        "//:npm_deps",
    ],
    args = [
        "build",
        "--config",
        "vite.config.pages.mjs",
    ],
    chdir = package_name(),
    out_dirs = ["dist-pages"],
)

vite_bin.vite_binary(
    name = "prototype_dev_server",
    args = [
        "--config",
        "vite.config.pages.mjs",
        "--port",
        "5273",
        "--strictPort",
    ],
    chdir = package_name(),
    data = [
        ":all_srcs",
        ":prototype_files",
        "//:npm_deps",
    ],
    tags = ["ibazel_notify_changes"],
)

# Build: Use bazel build //frontend:dist to generate production-ready static assets.
# Development: Use bazel run //frontend:dev_server (with ibazel) for rapid iterative development.
# Preview: Use bazel run //frontend:vite_preview to locally preview the production build.
# Prototypes without a backend: bazel run //frontend:prototype_dev_server
