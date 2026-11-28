#!/usr/bin/env bash
# Step 2 of the Gerrit archive: load the CSVs from export.sh into
# code_weekly_stats. Needs psql and the migration that creates the table.
#   bash tools/gerrit_archive/load.sh '<postgres url>'            dry run, rolls back
#   bash tools/gerrit_archive/load.sh '<postgres url>' --commit   keeps it
# Reads from OUT_DIR (default $HOME), the same directory export.sh wrote to.
set -euo pipefail
url=${1:?usage: load.sh '<postgres url>' [--commit]}
OUT_DIR=${OUT_DIR:-$HOME}
rows="$OUT_DIR/gerrit-archive.csv"
globals="$OUT_DIR/gerrit-archive-globals.csv"
for f in "$rows" "$globals"; do [[ -r "$f" ]] || { echo "missing $f; run export.sh first" >&2; exit 1; }; done
sql=$(mktemp)
trap 'rm -f "$sql"' EXIT
sed -e "s|__ROWS_FILE__|$rows|" -e "s|__GLOBALS_FILE__|$globals|" \
  "$(dirname "$0")/load.sql" >"$sql"
commit_args=()
[[ "${2:-}" == "--commit" ]] && commit_args=(-v commit=1)
psql "$url" -v ON_ERROR_STOP=1 "${commit_args[@]}" -f "$sql"
