#!/usr/bin/env bash
set -euo pipefail

: "${AUTH0_DOMAIN:? AUTH0_DOMAIN is not set}"
: "${AUTH0_MGMT_TOKEN:? AUTH0_MGMT_TOKEN is not set}"

# Fill in user emails here
USERS=(
  "example1@outlook.com"
  "example2@outlook.com"
)

RESPONSE_FILE=$(mktemp)
trap 'rm -f "$RESPONSE_FILE"' EXIT

for EMAIL in "${USERS[@]}"; do
  echo "Creating user: $EMAIL"

  HTTP_CODE=$(curl -s -w "%{http_code}" \
    -X POST "https://${AUTH0_DOMAIN}/api/v2/users" \
    -H "Authorization: Bearer ${AUTH0_MGMT_TOKEN}" \
    -o "$RESPONSE_FILE" \
    --json "{
      \"email\": \"${EMAIL}\",
      \"connection\": \"email\",
      \"email_verified\": true
    }")

  if [[ "$HTTP_CODE" == "201" ]]; then
    echo "Success: $EMAIL"
  elif [[ "$HTTP_CODE" == "409" ]]; then
    echo "Skip: $EMAIL already exists"
  else
    echo "Failed: $HTTP_CODE"
    cat "$RESPONSE_FILE"
    echo -e "\n-----------------------------------"
  fi
done