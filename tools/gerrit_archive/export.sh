#!/usr/bin/env bash
# Step 1 of the Gerrit archive: export every per-project weekly Gerrit bucket
# from Redis to CSV. Read-only against Redis.
#
#   NS=purrf-prod SECRET=purrf-prod bash tools/gerrit_archive/export.sh
#
# Needs kubectl access to the namespace's secret and redis-cli.
# Writes to OUT_DIR (default $HOME), chmod 600 since they name people:
#   gerrit-archive.csv          account,repo,week_start,merged,loc_merged,reviewed,closed
#                               from gerrit:stats:{ldap}:{project}:{week}
#   gerrit-archive-globals.csv  account,week_start,merged,loc_merged,reviewed,closed
#                               from gerrit:stats:{ldap}:{week}, used only to
#                               check the per-project rows add up
# Step 2 loads them: tools/gerrit_archive/load.sh
set -euo pipefail

NS=${NS:-purrf-prod}
SECRET=${SECRET:-purrf-prod}
TLS_ARGS=${REDIS_TLS_ARGS:---tls}
OUT_DIR=${OUT_DIR:-$HOME}
OUT="$OUT_DIR/gerrit-archive.csv"
GLOBALS="$OUT_DIR/gerrit-archive-globals.csv"

secret_value() {
  kubectl -n "$NS" get secret "$SECRET" -o "jsonpath={.data.$1}" | base64 -d
}

REDIS_HOST=$(secret_value REDIS_HOST)
REDIS_PORT=$(secret_value REDIS_PORT)
REDISCLI_AUTH=$(secret_value REDIS_PASSWORD)
export REDISCLI_AUTH
if [[ -z "$REDIS_HOST" || -z "$REDIS_PORT" ]]; then
  echo "REDIS_HOST/REDIS_PORT not found in secret $NS/$SECRET" >&2
  exit 1
fi

rc() {
  # shellcheck disable=SC2086
  redis-cli $TLS_ARGS -h "$REDIS_HOST" -p "$REDIS_PORT" --no-auth-warning "$@"
}

keys=$(mktemp)
project_keys=$(mktemp)
global_keys=$(mktemp)
values=$(mktemp)
trap 'rm -f "$keys" "$project_keys" "$global_keys" "$values"' EXIT

rc --scan --pattern 'gerrit:stats:*' --count 1000 | sort -u >"$keys"
# Plain character classes only: mawk has no {n} intervals.
awk -F: '$1 == "gerrit" && $2 == "stats" && NF == 5 && $5 ~ /^[0-9-]+_[0-9-]+$/' "$keys" >"$project_keys"
awk -F: '$1 == "gerrit" && $2 == "stats" && NF == 4 && $4 ~ /^[0-9-]+_[0-9-]+$/' "$keys" >"$global_keys"
odd=$(awk -F: '$1 == "gerrit" && $2 == "stats" && NF > 5' "$keys" | wc -l)
if [[ "$odd" -ne 0 ]]; then
  echo "$odd gerrit:stats keys have more than 5 segments (a ':' in a project name?); stopping." >&2
  exit 1
fi
echo "per-project buckets: $(wc -l <"$project_keys"); per-person buckets: $(wc -l <"$global_keys")" >&2

fields="cl_merged loc_merged cl_reviewed cl_abandoned"
umask 077

# One connection for all HMGETs; four reply lines per key, in key order.
awk -v f="$fields" '{ print "HMGET " $0 " " f }' "$project_keys" | rc --raw >"$values"
echo "account,repo,week_start,merged,loc_merged,reviewed,closed" >"$OUT"
paste -d: "$project_keys" <(paste -d: - - - - <"$values") | awk -F: '
  { printf "%s,%s,%s,%d,%d,%d,%d\n", $3, $4, substr($5, 1, 10), $6, $7, $8, $9 }
' >>"$OUT"

awk -v f="$fields" '{ print "HMGET " $0 " " f }' "$global_keys" | rc --raw >"$values"
echo "account,week_start,merged,loc_merged,reviewed,closed" >"$GLOBALS"
paste -d: "$global_keys" <(paste -d: - - - - <"$values") | awk -F: '
  { printf "%s,%s,%d,%d,%d,%d\n", $3, substr($4, 1, 10), $5, $6, $7, $8 }
' >>"$GLOBALS"

echo "wrote $OUT ($(($(wc -l <"$OUT") - 1)) rows) and $GLOBALS ($(($(wc -l <"$GLOBALS") - 1)) rows)" >&2
