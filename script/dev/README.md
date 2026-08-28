# Fake leave data for local development

Two halves of one fixture. Run both, in this order, with the `@circlecat.org`
address you sign in with:

```bash
export DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/db'

./script/dev/leave_seed.sh       you@circlecat.org
./script/dev/leave_seed_redis.sh you@circlecat.org
```

It has to be the same address both times: the join between an Azure ldap and a
purrf account is that address, and nothing else connects them.

Both read the environment the backend already uses. `leave_seed.sh` takes
`DATABASE_URL` and translates it for psql, which understands neither
SQLAlchemy's `+asyncpg` nor asyncpg's `ssl=` parameter. `leave_seed_redis.sh`
takes `REDIS_HOST`, `REDIS_PORT` and `REDIS_PASSWORD`, and connects with TLS —
the backend hardcodes `ssl=True`, so any Redis it can use speaks TLS. With no
`REDIS_HOST` set it falls back to a plain local `redis-cli`.

Two escape hatches: `REDIS_TLS=false` for a Redis without TLS, and `REDIS_CLI`
to replace the whole command for anything else — a CA file, a socket:

```bash
REDIS_CLI="redis-cli -h host -p 6379 -a secret --tls --cacert ca.pem" \
    ./script/dev/leave_seed_redis.sh you@circlecat.org
```

**Never run either against staging or production.**

## Why both

Employment facts — level, hire date, manager — live only in the Redis cache the
nightly Azure sync writes. Postgres holds no column for any of them. Seed the
database alone and every screen is still empty: the accrual engine walks the
Redis hash to find people, the all-hands table is built from it, and filing a
request looks the approver up in it.

## What you get

Five people, the 2026 company holidays (23 days, the real calendar), 110 ledger
rows and six requests.

| Person | Balance | What it is there for |
|---|---|---|
| You (L3) | 64.36 | One row of each of the six entry types, plus 34 weekly accruals |
| Bob Li (L4) | 64.36 | Your manager, and has none of his own — the data-health page's "No manager in Azure" column. He cannot file anything |
| Frank Sun (L2) | 44.36 | Reports to you |
| Dan Zhao (L1) | −16.00 | No annual entitlement, so permanently negative. Negative is expected, never an error colour |
| Erin Guo | 0 | Job title carries no level, so she accrues nothing while looking like an L1 |

The requests cover every status a screen shows: two waiting (one of them yours,
one waiting on your decision), three approved — including sick leave with
`decided_by` empty, which is what "approved by rule, not by a person" looks
like — and one rejected.

Both scripts can be run again. They look people up by address before creating
them, and clear their own ledger and request rows first.

## Before any of it shows up

- **The LaunchDarkly flag `leave-management` has to be on for your account.**
  The feature fails closed: until the flag answers, the dashboard card, all
  four routes and the admin page render nothing, and typing the address does
  not get you in either.
- **The backend needs a full `.env`.** `AppDependencyBuilder` constructs the
  Gerrit, Jira, LaunchDarkly, Microsoft, Google and Redis clients in its
  constructor, and each raises immediately when its variables are missing.
- **An empty database takes `bazel run //tools:init_db`**, not `migrate_db`,
  which cannot run against a database with no schema.

## On a shared environment

Anywhere the nightly ldap sync actually runs, the Redis profiles are deleted
the next time it fires: it drops every ldap Azure did not return, and these
five are invented. The database half survives; the Redis half does not.
