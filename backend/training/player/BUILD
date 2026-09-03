load("@aspect_bazel_lib//lib:copy_file.bzl", "copy_file")
load("@aspect_bazel_lib//lib:directory_path.bzl", "directory_path")

package(default_visibility = ["//visibility:public"])

# node_modules/scorm-again is linked as one directory, so a single file inside
# it needs a directory_path indirection to get a label copy_file can take.
directory_path(
    name = "scorm12_min_js_path",
    directory = "//:node_modules/scorm-again/dir",
    path = "dist/scorm12.min.js",
)

# The shim comes out of the npm package rather than a checked-in copy, so
# package.json stays the single place the version is written down.
copy_file(
    name = "scorm12_min_js",
    src = ":scorm12_min_js_path",
    out = "scorm12.min.js",
)

# Plain ESM, loaded by the browser as-is. It lives under frontend/src so the
# vitest suite can unit-test it; it is copied here so the backend image carries
# it, because it must be served from the content origin, not from Pages.
copy_file(
    name = "bridge_js",
    src = "//frontend/src/training:scorm_bridge",
    out = "bridge.js",
)

filegroup(
    name = "player_files",
    srcs = [
        "player.html",
        ":bridge_js",
        ":scorm12_min_js",
    ],
)
