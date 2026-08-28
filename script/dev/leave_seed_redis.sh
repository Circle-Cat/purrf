#!/usr/bin/env bash
#
# The other half of the fake leave data: the employment profiles the feature
# reads out of Redis.
#
# Azure is the only source of employment facts, and the nightly sync caches
# them under one hash. Nothing about a person's level, hire date or manager
# lives in postgres, so seeding the database alone leaves every leave screen
# empty: the accrual engine walks this hash, the all-hands table is built from
# it, and filing a request looks the approver up in it.
#
# Run it against your Redis after leave_seed.sh.
#
#   ./script/dev/leave_seed_redis.sh you@circlecat.org
#
# NEVER run this against staging or production. On any environment where the
# nightly ldap sync actually runs, these rows are deleted the next time it
# fires -- it drops every ldap Azure did not return.

set -euo pipefail

# The same account leave_seed.sh was pointed at. A full address is accepted and
# cut down to its local part: the hash is keyed by Azure ldap, and the join
# between an ldap and a purrf account is that corporate address.
ME="${1:-${LEAVE_SEED_EMAIL:-}}"

if [[ -z "$ME" ]]; then
    echo "usage: $0 <your-address@circlecat.org>" >&2
    echo "       (or set LEAVE_SEED_EMAIL)" >&2
    exit 2
fi

ME="${ME%%@*}"

# Which Redis, and how to reach it.
#
# REDIS_HOST, REDIS_PORT and REDIS_PASSWORD are the same three the backend
# reads, so an environment already configured for the app needs nothing more.
# TLS is on by default whenever a host is given: the backend connects with
# ssl=True and no way to turn it off, so a Redis it can use is a Redis that
# speaks TLS. Set REDIS_TLS=false for one that does not.
#
# With no host at all this falls back to a plain local redis-cli. REDIS_CLI
# overrides the lot -- for a client needing a CA file, a socket, or anything
# else this does not spell:
#
#   REDIS_CLI="redis-cli -h host -p 6379 -a secret --tls --cacert ca.pem"
if [[ -n "${REDIS_CLI:-}" ]]; then
    read -r -a REDIS <<< "$REDIS_CLI"
elif [[ -n "${REDIS_HOST:-}" ]]; then
    REDIS=(redis-cli -h "$REDIS_HOST" -p "${REDIS_PORT:-6379}")
    if [[ -n "${REDIS_PASSWORD:-}" ]]; then
        REDIS+=(-a "$REDIS_PASSWORD" --no-auth-warning)
    fi
    if [[ "${REDIS_TLS:-true}" != "false" ]]; then
        REDIS+=(--tls)
    fi
else
    REDIS=(redis-cli)
fi
KEY=leave:employment

# level      -- L1 has no annual entitlement, L2 to L4 get 80 hours a year.
# annual_hours -- what the engine pays towards; it does not re-derive it.
# hire_date  -- where accrual starts counting, as a Beijing calendar date.
# leave_date -- null while they are still here.
# manager_ldap -- who approves for them. Missing means they cannot file
#                 anything at all, sick leave included.
# problems   -- what the data-health page lists them under.

# You: an L3 with a manager, so you can file requests.
"${REDIS[@]}" HSET "$KEY" "$ME" '{"account_enabled": true, "annual_hours": 80, "hire_date": "2024-03-04", "leave_date": null, "level": "L3", "manager_ldap": "bob.li", "problems": []}'

# Your manager. He is at the top of the tree with nobody above him, which is
# what the "No manager in Azure" column on the data-health page is for -- and
# it means Bob himself cannot file a request.
"${REDIS[@]}" HSET "$KEY" bob.li '{"account_enabled": true, "annual_hours": 80, "hire_date": "2021-06-01", "leave_date": null, "level": "L4", "manager_ldap": null, "problems": ["missing_manager"]}'

# Reports to you. An L1: no entitlement, so no accrual rows and a permanently
# negative balance once he takes paid leave. Expected, not broken.
"${REDIS[@]}" HSET "$KEY" dan.zhao '{"account_enabled": true, "annual_hours": 0, "hire_date": "2025-09-15", "leave_date": null, "level": "L1", "manager_ldap": "'"$ME"'", "problems": []}'

# Reports to you. Ordinary L2.
"${REDIS[@]}" HSET "$KEY" frank.sun '{"account_enabled": true, "annual_hours": 80, "hire_date": "2023-01-10", "leave_date": null, "level": "L2", "manager_ldap": "'"$ME"'", "problems": []}'

# Reports to you, but her Azure job title does not parse into a level, so she
# accrues nothing while looking exactly like an L1 in the figures. The
# data-health page exists to tell those two apart.
"${REDIS[@]}" HSET "$KEY" erin.guo '{"account_enabled": true, "annual_hours": 0, "hire_date": "2024-11-04", "leave_date": null, "level": null, "manager_ldap": "'"$ME"'", "problems": ["unparseable_job_title"]}'

echo
echo "Profiles now in $KEY:"
"${REDIS[@]}" HKEYS "$KEY"
