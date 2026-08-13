load("@aspect_rules_js//js:defs.bzl", "js_library")

package(default_visibility = ["//visibility:public"])

# Cross-language test fixtures. Each is consumed by a py_test and a
# vitest_test so one file defines the behaviour both implementations of a
# mirrored rule must satisfy.
filegroup(
    name = "form_visibility_vectors",
    srcs = ["form_visibility_vectors.json"],
)

js_library(
    name = "form_visibility_vectors_js",
    srcs = ["form_visibility_vectors.json"],
)

filegroup(
    name = "application_stages_vector",
    srcs = ["application_stages.json"],
)

js_library(
    name = "application_stages_vector_js",
    srcs = ["application_stages.json"],
)
