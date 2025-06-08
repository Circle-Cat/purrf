load("@aspect_bazel_lib//lib:transitions.bzl", "platform_transition_filegroup")
load("@pypi//:requirements.bzl", "requirement")
load("@rules_oci//oci:defs.bzl", "oci_load", "oci_push")
load("@rules_python//python:defs.bzl", "py_library")
load("//:py_layer.bzl", "py_oci_image")

package(default_visibility = ["//purrf:__subpackages__"])

exports_files(
    [
        ".ruff.toml",
    ],
    visibility = ["//tools/lint:lint_access_file_group"],  #lint file group
)

alias(
    name = "format",
    actual = "//tools/format",
)

py_library(
    name = "all_files",
    srcs = glob(
        ["**/*.py"],
        allow_empty = True,
    ),
)

py_oci_image(
    name = "purrf_image",
    base = "@python_base",
    binary = "//src:uvicorn",
    cmd = [
        "--host=0.0.0.0",
        "--port=5001",
    ],
    entrypoint = [
        "/src/uvicorn",
        "src.app:asgi_app",
    ],
)

platform(
    name = "aarch64_linux",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:aarch64",
    ],
)

platform(
    name = "x86_64_linux",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
)

platform_transition_filegroup(
    name = "platform_image",
    srcs = [":purrf_image"],
    target_platform = select({
        "@platforms//cpu:arm64": ":aarch64_linux",
        "@platforms//cpu:x86_64": ":x86_64_linux",
    }),
)

# (auto) generate REPO,TAG files for dynamic oci_push
genrule(
    name = "dynamic_repository",
    outs = ["final_repository.txt"],
    cmd = """
    REPO=$${REPO:-index.docker.io/alice/repo}  # nonexistent REPO; please pass in real REPO through environment parameters
    echo "$$REPO" > $@
    """,
)

genrule(
    name = "dynamic_tags",
    outs = ["final_tags.txt"],
    cmd = """
    TAG_1=$${TAG_1:-latest} # if TAG not defined, use default value; or pass in TAG through environment parameters
    TAG_2=$${TAG_2:-latest}

    echo "$$TAG_1" > $@
    echo "$$TAG_2" >> $@
    """,
)

# dynamic oci_push
oci_push(
    name = "purrf_image_push_dynamic",
    image = ":platform_image",
    remote_tags = ":dynamic_tags",
    repository_file = ":dynamic_repository",
)
