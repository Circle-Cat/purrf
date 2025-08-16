#!/usr/bin/env bash
#
# Shows an end-to-end workflow for linting without failing the build.
# This is meant to mimic the behavior of the `bazel lint` command that you'd have
# by using the Aspect CLI [lint command](https://docs.aspect.build/cli/commands/aspect_lint).
#
# To make the build fail when a linter warning is present, run with `--fail-on-violation`.
# To auto-fix violations, run with `--fix` (or `--fix --dry-run` to just print the patches)
#
# NB: this is an example of code you could paste into your repo, meaning it's userland
# and not a supported public API of rules_lint. It may be broken and we don't make any
# promises to fix issues with using it.
# We recommend using Aspect CLI instead!
#
# Examples:
#   1. Lint all default targets (auto-query):
#        ./lint.sh check_all
#
#   2. Lint specific targets:
#        ./lint.sh //frontend/... //backend:api_lib
#
#   3. Lint in auto-fix mode (auto-query):
#        ./lint.sh --fix check_all
#
#   4. Lint in auto-fix mode for specific targets:
#        ./lint.sh --fix //frontend:app_lib
#

set -o errexit -o pipefail -o nounset

if [ "$#" -eq 0 ]; then
	echo "No targets specified. You can use 'check_all' to lint all default targets."
    echo "Example usages:"
    echo "  ./lint.sh check_all                # Lint all default targets"
    echo "  ./lint.sh --fix check_all          # Lint and auto-fix all targets"
    echo "  ./lint.sh //frontend/...           # Lint specific targets"
    echo "  ./lint.sh --fix //frontend:app_lib # Lint and auto-fix specific targets"
    exit 1
fi

# Regex pattern to match Bazel target kinds that should be linted.
# This includes targets ending with _test, _binary, or _library.
TARGET_KINDS='".*_(test|binary|library)"'

# Bazel package paths to search for targets.
# This includes backend, frontend, and test directories.
TARGET_PATHS='//backend/... + //frontend/... + //tests/...'

args_without_all=()
need_all=false

# Iterate through input arguments
for arg in "$@"; do
    if [ "$arg" == "check_all" ]; then
        need_all=true
    else
        args_without_all+=("$arg")
    fi
done

# If "check_all" was requested, query all Bazel targets
if [ "$need_all" = true ]; then
    echo "Querying all files..."
    readarray -t all_targets < <(bazel query "kind($TARGET_KINDS, $TARGET_PATHS)" | sort -u)
    if [ "${#all_targets[@]}" -eq 0 ]; then
        echo "No targets found with the query. Exiting."
        exit 1
    fi
	# Append the queried targets to the argument list
    args_without_all+=("${all_targets[@]}")
fi

# Reset positional parameters to the new argument list
set -- "${args_without_all[@]}"

echo "Final arguments:"
printf '  %s\n' "$@"

fix=""
buildevents=$(mktemp)
filter='.namedSetOfFiles | values | .files[] | select(.name | endswith($ext)) | ((.pathPrefix | join("/")) + "/" + .name)'
unameOut="$(uname -s)"
case "${unameOut}" in
Linux*) machine=Linux ;;
Darwin*) machine=Mac ;;
CYGWIN*) machine=Windows ;;
MINGW*) machine=Windows ;;
MSYS_NT*) machine=Windows ;;
*) machine="UNKNOWN:${unameOut}" ;;
esac
args=()
args=("--aspects=$(echo //tools/lint:linters.bzl%{ruff,eslint} | tr ' ' ',')")
args+=(
	# Allow lints of code that fails some validation action
	# See https://github.com/aspect-build/rules_ts/pull/574#issuecomment-2073632879
	"--norun_validations"
	"--build_event_json_file=$buildevents"
	"--output_groups=rules_lint_human"
	"--remote_download_regex='.*AspectRulesLint.*'"
)
# Allow a `--fix` option on the command-line.
# This happens to make output of the linter such as ruff's
# [*] 1 fixable with the `--fix` option.
# so that the naive thing of pasting that flag to lint.sh will do what the user expects.
if [ $1 == "--fix" ]; then
	fix="patch"
	args+=(
		"--@aspect_rules_lint//lint:fix"
		"--output_groups=rules_lint_patch"
	)
	shift
fi
# Run linters
bazel --max_idle_secs=10 build ${args[@]} $@
JQ_URL="https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64"
JQ_CHECKSUM="af986793a515d500ab2d35f8d2aecd656e764504b789b66d7e1a0b727a124c44"
JQ_BIN=$(mktemp)
trap 'rm -rf -- "$JQ_BIN"' EXIT
if command -v jq &> /dev/null; then
	JQ_CMD="jq"
else
	curl -L -o "$JQ_BIN" "$JQ_URL" || { echo "Download failed! Exiting..."; exit 1; }
	if ! echo "$JQ_CHECKSUM  $JQ_BIN" | sha256sum --check --status; then
		echo "Checksum verification failed! Exiting..."
		exit 1
	fi
	chmod +x "$JQ_BIN"
	JQ_CMD="$JQ_BIN"
fi
valid_reports=$("$JQ_CMD" --arg ext .out --raw-output "$filter" "$buildevents" | tr -d '\r')
has_failure=0
# Show the results.
while IFS= read -r report; do
	# Exclude coverage reports, and check if the output is empty.
	if [[ "$report" == *coverage.dat ]] || [[ ! -s "$report" ]]; then
		# Report is empty. No linting errors.
		continue
	fi
	echo "From ${report}:"
	cat "${report}"
	if ! grep -q "All checks passed!" "${report}"; then
		has_failure=1
	fi
done <<<"$valid_reports"
if [ -n "$fix" ]; then
	valid_patches=$("$JQ_CMD" --arg ext .patch --raw-output "$filter" "$buildevents" | tr -d '\r')
	while IFS= read -r patch; do
		# Exclude coverage, and check if the patch is empty.
		if [[ "$patch" == *coverage.dat ]] || [[ ! -s "$patch" ]]; then
			# Patch is empty. No linting errors.
			continue
		fi
		case "$fix" in
		"print")
			echo "From ${patch}:"
			cat "${patch}"
			echo
			;;
		"patch")
			patch -p1 <${patch}
			;;
		*)
			echo >2 "ERROR: unknown fix type $fix"
			exit 1
			;;
		esac
	done <<<"$valid_patches"
fi
# Exit with failure if any report failed
exit $has_failure
